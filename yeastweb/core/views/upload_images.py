from django.shortcuts import render, redirect
from core.forms import UploadImageForm
from core.models import UploadedImage, DVLayerTifPreview
from .utils import tif_to_jpg, write_progress
from pathlib import Path    
from yeastweb.settings import MEDIA_ROOT
from .variables import PRE_PROCESS_FOLDER_NAME
from mrc import DVFile
from PIL import Image
import uuid
import numpy as np
import skimage.exposure
import json
from django.contrib import messages
from django.http import JsonResponse
from ..metadata_processing.dv_channel_parser import extract_channel_config
from ..metadata_processing.error_handling import (
    DVValidationOptions,
    DVValidationResult,
    build_dv_error_messages,
    validate_dv_file,
)
from ..stats_plugins import (
    CHANNEL_ORDER,
    build_plugin_ui_payload,
    build_requirement_summary,
    normalize_selected_plugins,
)
import uuid as uuid_lib


def _parse_bool(value, default=False):
    """Parse a POST boolean value with a safe default."""

    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _parse_channels(raw_values) -> set[str]:
    """Parse channel values from either list or comma-delimited payload."""

    if raw_values is None:
        return set()
    if isinstance(raw_values, str):
        values = [part.strip() for part in raw_values.split(",")]
    else:
        values = []
        for item in raw_values:
            if not isinstance(item, str):
                continue
            values.extend(part.strip() for part in item.split(","))
    allowed = set(CHANNEL_ORDER)
    return {value for value in values if value in allowed}


def _parse_restore_uuids(raw_values) -> list[str]:
    """Parse UUID values from list or comma-delimited payload preserving order."""

    if raw_values is None:
        return []
    if isinstance(raw_values, str):
        values = [part.strip() for part in raw_values.split(",")]
    else:
        values = []
        for item in raw_values:
            if not isinstance(item, str):
                continue
            values.extend(part.strip() for part in item.split(","))

    parsed: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not value:
            continue
        try:
            normalized = str(uuid_lib.UUID(value))
        except (TypeError, ValueError, AttributeError):
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        parsed.append(normalized)
    return parsed


def _upload_view_context(*, form, progress_key, error=None, restored_queue_items=None):
    """Build template context for the upload page."""

    context = {
        "form": form,
        "progress_key": progress_key,
        "stats_plugin_payload_json": json.dumps(build_plugin_ui_payload()),
        "restored_queue_payload_json": json.dumps(restored_queue_items or []),
    }
    if error:
        context["error"] = error
    return context


def upload_images(request):
    """
    Uploads and processes each image in the selected folder individually.
    Generates a unique UUID for each image and applies the same process to each one.
    """
    # Ensure session exists to derive a stable progress key
    if not request.session.session_key:
        request.session.save()
    progress_key = request.session.session_key

    if request.method == "POST":
        print("POST request received")
        
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        files = request.FILES.getlist('files')
        existing_uuids = _parse_restore_uuids(request.POST.getlist("existing_uuids"))

        if not files and not existing_uuids:
            print("No files received")
            return render(
                request,
                'form/uploadImage.html',
                _upload_view_context(
                    form=UploadImageForm(),
                    progress_key=progress_key,
                    error='No files received.',
                ),
            )

        print(f"Files received: {[file.name for file in files]}")

        selected_analysis = normalize_selected_plugins(request.POST.getlist("selected_analysis"))
        requirement_summary = build_requirement_summary(selected_analysis)

        gfp_distance_raw = request.POST.get("distance", "37")
        try:
            gfp_distance = int(gfp_distance_raw)
        except (TypeError, ValueError):
            gfp_distance = 37
        if gfp_distance < 0:
            gfp_distance = 37

        # Persist user analysis choices now so preprocess step no longer owns selection.
        request.session["selected_analysis"] = requirement_summary["selected_plugins"]
        request.session["distance"] = gfp_distance

        module_enabled = _parse_bool(request.POST.get("yeast_analysis_enabled"), default=False)
        enforce_layer_count = module_enabled and _parse_bool(
            request.POST.get("enforce_layer_count"),
            default=False,
        )
        enforce_wavelengths = module_enabled and _parse_bool(
            request.POST.get("enforce_wavelengths"),
            default=False,
        )

        # Optional per-channel toggles from advanced settings. Stats-required channels
        # are always enforced server-side regardless of these optional toggles.
        extra_required_channels = _parse_channels(request.POST.getlist("extra_required_channels"))
        required_channels = set(requirement_summary["required_channels"])
        if module_enabled:
            required_channels.update(extra_required_channels)

        validation_options = DVValidationOptions(
            enforce_layer_count=enforce_layer_count,
            enforce_wavelengths=enforce_wavelengths,
            required_channels=required_channels,
        )

        # Store all UUIDs of the processed images
        image_uuids = []
        validation_failures = []

        # Validate any restored queue UUIDs first to preserve order.
        for existing_uuid in existing_uuids:
            try:
                existing_image = UploadedImage.objects.get(uuid=existing_uuid)
            except UploadedImage.DoesNotExist:
                validation_failures.append(
                    (
                        existing_uuid,
                        DVValidationResult(
                            is_valid=False,
                            layer_count=None,
                            missing_channels=set(),
                            required_channels=set(required_channels),
                            error_message="no longer available in the upload queue",
                        ),
                    )
                )
                continue

            existing_dv_path = Path(MEDIA_ROOT) / str(existing_image.file_location)
            validation_result = validate_dv_file(existing_dv_path, validation_options)
            if not validation_result.is_valid:
                validation_failures.append((existing_image.name, validation_result))
                continue
            image_uuids.append(str(existing_uuid))

        # Iterate through each newly uploaded file and assign a unique UUID
        preprocess_marked = False
        for image_location in files:
            name = image_location.name
            name = Path(name).stem

            # Generate a UUID for the image
            image_uuid = uuid.uuid4()

            # Save the image instance with the generated UUID
            instance = UploadedImage(name=name, uuid=image_uuid, file_location=image_location)
            instance.save()


            # Validate metadata before any preprocessing setup.
            dv_file_path = Path(MEDIA_ROOT) / str(instance.file_location)
            validation_result = validate_dv_file(dv_file_path, validation_options)
            if not validation_result.is_valid:
                validation_failures.append((name, validation_result))
                instance.delete()
                continue

            # only valid files make it into the queue
            image_uuids.append(str(image_uuid))

            # Create a directory for each image based on its UUID
            output_dir = Path(MEDIA_ROOT, str(image_uuid))
            output_dir.mkdir(parents=True, exist_ok=True)

            # Extract and save the per-file channel configuration
            dv_file_path = Path(MEDIA_ROOT) / str(instance.file_location)
            channel_config = extract_channel_config(dv_file_path)
            config_json_path = output_dir / "channel_config.json"
            with open(config_json_path, "w") as config_file:
                json.dump(channel_config, config_file)

            # Define the directory for storing preprocessed images
            pre_processed_dir = output_dir / PRE_PROCESS_FOLDER_NAME
            stored_dv_path = Path(str(MEDIA_ROOT), str(instance.file_location))

            print(f"Processing file: {name}, UUID: {image_uuid}")

            # Apply the preprocessing step to each image
            if not preprocess_marked:
                write_progress(progress_key, "Preprocessing Images")
                preprocess_marked = True
            generate_tif_preview_images(stored_dv_path, pre_processed_dir, instance, 4)

        error_lines = build_dv_error_messages(validation_failures, validation_options)
        preprocess_url = None
        if image_uuids:
            preprocess_url = f'/image/preprocess/{",".join(map(str, image_uuids))}/'

        # Case 3: no valid files
        if not image_uuids:
            if error_lines:
                if is_ajax:
                    return JsonResponse({'errors': error_lines}, status=400)
                messages.error(request, "\n".join(error_lines))
                return redirect(request.path)
            msg = 'No valid DV files were uploaded. Please upload files that pass the selected checks.'
            if is_ajax:
                return JsonResponse({'errors': [msg]}, status=400)
            messages.error(request, msg)
            return redirect(request.path)

        # Case 2: some invalid files
        if error_lines:
            if is_ajax:
                return JsonResponse({'errors': error_lines, 'redirect': preprocess_url})
            messages.error(request, "\n".join(error_lines))

        # Case 1: all valid (or mixed after pushing messages)
        if is_ajax:
            return JsonResponse({'redirect': preprocess_url})
        return redirect(preprocess_url)
    else:
        form = UploadImageForm()
        restore_param = request.GET.get("restore", "")
        restore_uuids = _parse_restore_uuids(restore_param)
        restored_map = {
            str(item.uuid): item
            for item in UploadedImage.objects.filter(uuid__in=restore_uuids)
        }
        restored_queue_items = []
        for uid in restore_uuids:
            item = restored_map.get(uid)
            if not item:
                continue
            restored_queue_items.append(
                {
                    "uuid": uid,
                    "name": item.name,
                }
            )
    return render(
        request,
        'form/uploadImage.html',
        _upload_view_context(
            form=form,
            progress_key=progress_key,
            restored_queue_items=restored_queue_items if request.method != "POST" else None,
        ),
    )

def generate_tif_preview_images(dv_path :Path, save_path :Path, uploaded_image : UploadedImage, n_layers : int ):
    """
        Converts DV's layers into tif files
    """
    dv_file = DVFile(dv_path)
    try:
        arr = dv_file.asarray()
    finally:
        dv_file.close()

    if arr.ndim == 2:
        layers = np.expand_dims(arr, axis=0)
    elif arr.ndim == 3:
        # Use the smallest axis as the Z dimension for layer extraction.
        z_axis = int(np.argmin(arr.shape))
        layers = np.moveaxis(arr, z_axis, 0)
    else:
        print(f"Unexpected DV array rank {arr.ndim} for {dv_path}")
        return

    actual_layers = layers.shape[0]
    if actual_layers != n_layers:
        # Prevent huge loops when DV files don't match the expected layer count.
        print(f'Uploaded Dv file layers do not match n_layers {n_layers}')
        n_layers = actual_layers

    for i in range(n_layers):
        dv = layers[i]
        # using the pre_preprocess methods from mrcnn because else the dv layers are essentially entirely black to the eye
        image = Image.fromarray(dv)
        # Preprocessing operations
        image = skimage.exposure.rescale_intensity(np.float32(image), out_range=(0, 1))
        image = np.round(image * 255).astype(np.uint8)        #convert to 8 bit
        image = np.expand_dims(image, axis=-1)
        rgb_image = np.tile(image, 3)                          #convert to RGB
        #rgbimage = skimage.filters.gaussian(rgbimage, sigma=(1,1))   # blur it first?

        rgb_image = Image.fromarray(rgb_image)
        save_path.mkdir(parents=True, exist_ok=True)
        tif_path = save_path / f"preprocess-image{i}.tif"
        rgb_image.save(str(tif_path))
        jpg_path = tif_to_jpg(output_dir=save_path, tif_path=tif_path)
        # gets path relative to MEDIA ROOT for django
        # Ex. 0c51afb4-d8cb-43e5-a75c-8d4cc0f31a14\preprocessed_images\preprocess-image0.jpg
        file_location = jpg_path.relative_to(MEDIA_ROOT)
        instance = DVLayerTifPreview(
            wavelength='',
            uploaded_image_uuid=uploaded_image,
            file_location=str(file_location),
        )
        instance.save()

from django.shortcuts import get_object_or_404, get_list_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.template.response import TemplateResponse
from django.utils import inspect
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.contrib import messages
import sys, pkgutil, importlib, inspect

from core.models import DVLayerTifPreview, UploadedImage
from core.mrcnn.my_inference import predict_images
from core.mrcnn.preprocess_images import preprocess_images
from .utils import (
    tif_to_jpg,
    write_progress,
    progress_path,
    read_progress,
    is_cancelled,
    set_cancelled,
    clear_cancelled,
)
from core.metadata_processing.dv_channel_parser import extract_channel_config
from core.cell_analysis import Analysis
from core.contour_processing import (
    MCHERRY_DOT_METHOD_CURRENT,
    normalize_mcherry_dot_method,
)
from core.config import DEFAULT_PROCESS_CONFIG

from yeastweb.settings import MEDIA_ROOT, BASE_DIR
from pathlib import Path
import json
import re
import hashlib

LEGACY_GFP_MIN_AREA_DEFAULT = float(DEFAULT_PROCESS_CONFIG.get("legacy_gfp_min_area", 14.0))
LEGACY_GFP_MAX_COUNT_DEFAULT = int(DEFAULT_PROCESS_CONFIG.get("legacy_gfp_max_count", 8))
LEGACY_GFP_OTSU_BIAS_DEFAULT = float(DEFAULT_PROCESS_CONFIG.get("legacy_gfp_otsu_bias", 0.0))


def _parse_float(value, default, minimum=None, maximum=None):
    """Parse a float input with optional clamping."""
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = float(default)
    if minimum is not None:
        parsed = max(minimum, parsed)
    if maximum is not None:
        parsed = min(maximum, parsed)
    return parsed


def _parse_int(value, default, minimum=None, maximum=None):
    """Parse an integer input with optional clamping."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = int(default)
    if minimum is not None:
        parsed = max(minimum, parsed)
    if maximum is not None:
        parsed = min(maximum, parsed)
    return parsed



def load_analyses(path:str) -> list:
    """
    This function dynamically load the list of analyses from the path folder
    :param path: Path the analysis folder
    :return: List of the name of the analyses
    """
    analyses = []
    sys.path.append(str(path))
    print(path)

    modules = pkgutil.iter_modules(path=[path])
    for loader, mod_name, ispkg in modules:
        # Ensure that module isn't already loaded
        loaded_mod = None
        if mod_name not in sys.modules:
            # Import module
            loaded_mod = importlib.import_module('.cell_analysis','core')
        if loaded_mod is None: continue
        if mod_name != 'Analysis':
            loaded_class = getattr(loaded_mod, mod_name)
            instanceOfClass = loaded_class()
            if isinstance(instanceOfClass, Analysis):
                print('Added Plugin -- ' + mod_name)
                analyses.append(mod_name)
            else:
                print
                mod_name + " was not an instance of Analysis"

    return analyses


@require_GET
def get_progress(request, uuids):
    try:
        # Basic validation: non-empty and only hex/commas/dashes
        if not uuids or not re.fullmatch(r"[0-9a-fA-F,-]+", uuids):
            return JsonResponse({"phase": "idle"})
        path = progress_path(uuids)
        if path.exists():
            data = json.loads(path.read_text() or '{}')
            return JsonResponse({"phase": data.get("phase", "idle")})
        return JsonResponse({"phase": "idle"})
    except Exception as e:
        return JsonResponse({"phase": "idle"})


def pre_process_step(request, uuids):
    """
    GET: Render previews + sidebar (with auto-detected channel order).
    POST: Run preprocess + inference on every UUID, then redirect.
    """

    path = BASE_DIR / 'core/cell_analysis'
    analyses_list = load_analyses(path)
    print(analyses_list)

    uuid_list = uuids.split(',')
    total_files = len(uuid_list)

    # clamp file_index into [0, total_files-1]
    current_file_index = int(request.GET.get('file_index', 0))
    current_file_index = max(0, min(current_file_index, total_files - 1))

    # build sidebar list, including the 4-channel order per file
    file_list = []
    for uid in uuid_list:
        uploaded = get_object_or_404(UploadedImage, uuid=uid)

        # try reading existing channel_config.json
        cfg_path = Path(MEDIA_ROOT) / uid / 'channel_config.json'
        if cfg_path.exists():
            cfg = json.loads(cfg_path.read_text())
            detected_channels = [ch for ch, _ in sorted(cfg.items(), key=lambda t: t[1])]
        else:
            # fallback: parse header of first .dv file
            dv_files = list((Path(MEDIA_ROOT) / uid).glob('*.dv'))
            if dv_files:
                cfg = extract_channel_config(str(dv_files[0]))
                detected_channels = [ch for ch, _ in sorted(cfg.items(), key=lambda t: t[1])]
            else:
                detected_channels = []

        file_list.append({
            'uuid': uid,
            'name': uploaded.name,
            'detected_channels': detected_channels,
        })

    # current file previews
    current_uuid = uuid_list[current_file_index]
    uploaded_image = get_object_or_404(UploadedImage, uuid=current_uuid)
    preview_images = get_list_or_404(DVLayerTifPreview, uploaded_image_uuid=current_uuid)

    # POST: preprocess + predict all, then redirect
    if request.method == "POST":
        clear_cancelled(uuids)
        selected_analysis = request.POST.getlist('selected_analysis')
        gfp_distance = request.POST.get('distance', 37)
        mcherry_dot_method = normalize_mcherry_dot_method(
            request.POST.get('mCherry_dot_method', MCHERRY_DOT_METHOD_CURRENT)
        )
        legacy_gfp_min_area_default = _parse_float(
            request.session.get('legacy_gfp_min_area', LEGACY_GFP_MIN_AREA_DEFAULT),
            LEGACY_GFP_MIN_AREA_DEFAULT,
            minimum=0.0,
            maximum=500.0,
        )
        legacy_gfp_max_count_default = _parse_int(
            request.session.get('legacy_gfp_max_count', LEGACY_GFP_MAX_COUNT_DEFAULT),
            LEGACY_GFP_MAX_COUNT_DEFAULT,
            minimum=1,
            maximum=100,
        )
        legacy_gfp_otsu_bias_default = _parse_float(
            request.session.get('legacy_gfp_otsu_bias', LEGACY_GFP_OTSU_BIAS_DEFAULT),
            LEGACY_GFP_OTSU_BIAS_DEFAULT,
            minimum=-80.0,
            maximum=80.0,
        )
        legacy_gfp_min_area = _parse_float(
            request.POST.get('legacy_gfp_min_area', legacy_gfp_min_area_default),
            legacy_gfp_min_area_default,
            minimum=0.0,
            maximum=500.0,
        )
        legacy_gfp_max_count = _parse_int(
            request.POST.get('legacy_gfp_max_count', legacy_gfp_max_count_default),
            legacy_gfp_max_count_default,
            minimum=1,
            maximum=100,
        )
        legacy_gfp_otsu_bias = _parse_float(
            request.POST.get('legacy_gfp_otsu_bias', legacy_gfp_otsu_bias_default),
            legacy_gfp_otsu_bias_default,
            minimum=-80.0,
            maximum=80.0,
        )
        print("selected_analysis")
        print(selected_analysis)

        request.session['selected_analysis'] = selected_analysis  # save selected analysis to session
        request.session['distance'] = gfp_distance
        request.session['mCherry_dot_method'] = mcherry_dot_method
        request.session['legacy_gfp_min_area'] = legacy_gfp_min_area
        request.session['legacy_gfp_max_count'] = legacy_gfp_max_count
        request.session['legacy_gfp_otsu_bias'] = legacy_gfp_otsu_bias

        # Track when we first enter phases to mark progress once
        preprocess_marked = False
        detection_marked = False

        cancel_check = lambda: is_cancelled(uuids)
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        def cancel_response():
            if is_ajax:
                return JsonResponse({"status": "cancelled"})
            return HttpResponse("Cancelled", status=409)

        for image_uuid in uuid_list:
            if cancel_check():
                write_progress(uuids, "Cancelled")
                clear_cancelled(uuids)
                return cancel_response()
            img_obj = get_object_or_404(UploadedImage, uuid=image_uuid)
            out_dir = Path(MEDIA_ROOT) / image_uuid

            if not preprocess_marked:
                write_progress(uuids, "Preprocessing Images")
                preprocess_marked = True
            prep_path, prep_list = preprocess_images(
                image_uuid,
                img_obj,
                out_dir,
                cancel_check=cancel_check,
            )
            if cancel_check() or not prep_path or not prep_list:
                write_progress(uuids, "Cancelled")
                clear_cancelled(uuids)
                return cancel_response()
            tif_to_jpg(Path(prep_path), out_dir)

            if not detection_marked:
                write_progress(uuids, "Detecting Cells")
                detection_marked = True
            prediction_result = predict_images(
                prep_path,
                prep_list,
                out_dir,
                cancel_check=cancel_check,
            )
            if prediction_result is None or cancel_check():
                write_progress(uuids, "Cancelled")
                clear_cancelled(uuids)
                return cancel_response()

        return redirect(f'/image/{uuids}/convert/')

    # AJAX navigation
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'images': [
                {'file_location': {'url': img.file_location.url}}
                for img in preview_images
            ],
            'file_name': uploaded_image.name,
            'current_file_index': current_file_index,
        })

    selected_mcherry_dot_method = normalize_mcherry_dot_method(
        request.session.get('mCherry_dot_method', MCHERRY_DOT_METHOD_CURRENT)
    )
    selected_legacy_gfp_min_area = _parse_float(
        request.session.get('legacy_gfp_min_area', LEGACY_GFP_MIN_AREA_DEFAULT),
        LEGACY_GFP_MIN_AREA_DEFAULT,
        minimum=0.0,
        maximum=500.0,
    )
    selected_legacy_gfp_max_count = _parse_int(
        request.session.get('legacy_gfp_max_count', LEGACY_GFP_MAX_COUNT_DEFAULT),
        LEGACY_GFP_MAX_COUNT_DEFAULT,
        minimum=1,
        maximum=100,
    )
    selected_legacy_gfp_otsu_bias = _parse_float(
        request.session.get('legacy_gfp_otsu_bias', LEGACY_GFP_OTSU_BIAS_DEFAULT),
        LEGACY_GFP_OTSU_BIAS_DEFAULT,
        minimum=-80.0,
        maximum=80.0,
    )

    # Normal render
    return TemplateResponse(request, "pre-process.html", {
        'images': preview_images,
        'file_name': uploaded_image.name,
        'current_file_index': current_file_index,
        'total_files': total_files,
        'uuids': uuids,
        'file_list': file_list,
        'analyses' : analyses_list,
        'mcherry_dot_method': selected_mcherry_dot_method,
        'legacy_gfp_min_area': selected_legacy_gfp_min_area,
        'legacy_gfp_max_count': selected_legacy_gfp_max_count,
        'legacy_gfp_otsu_bias': selected_legacy_gfp_otsu_bias,
    })

@require_POST
def set_progress(request, key):
    try:
        body = json.loads(request.body or '{}')
    except Exception:
        body = {}
    phase = body.get('phase', 'idle')
    try:
        write_progress(key, phase)
        return JsonResponse({"status": "ok"})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@csrf_protect
@require_POST
def cancel_progress(request, uuids):
    try:
        if not uuids or not re.fullmatch(r"[0-9a-fA-F,-]+", uuids):
            return JsonResponse({"status": "invalid"}, status=400)
        data = read_progress(uuids)
        phase = data.get("phase", "idle")
        if phase in ("idle", "Completed", "Cancelled"):
            write_progress(uuids, "Cancelled")
            clear_cancelled(uuids)
            return JsonResponse({"status": "cancelled"})
        set_cancelled(uuids)
        write_progress(uuids, "Cancelling")
        return JsonResponse({"status": "cancelling"})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@require_POST
@csrf_exempt
def update_channel_order(request, uuid):
    """
    POST {order: ["DIC","DAPI","mCherry","GFP"]}
    → overwrite channel_config.json in MEDIA_ROOT/<uuid>/
    """
    try:
        data = json.loads(request.body)
        new_order = data.get('order', [])
        expected = {"mCherry", "GFP", "DAPI", "DIC"}
        if set(new_order) != expected:
            return JsonResponse({'error': 'invalid channel list'}, status=400)

        # new: 0–3 mapping to match your layer filenames
        mapping = {ch: i for i, ch in enumerate(new_order)}


        cfg_path = Path(MEDIA_ROOT) / uuid / 'channel_config.json'
        if not cfg_path.exists():
            return JsonResponse({'error': 'config not found'}, status=404)

        # SAVE: overwrite the JSON file with new mapping
        cfg_path.write_text(json.dumps(mapping))
        return JsonResponse({'status': 'ok'})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

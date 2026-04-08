import cv2
import logging
from pathlib import Path
from cytocv.settings import MEDIA_ROOT
from core.models import SegmentedImage, get_guest_user
from core.services.analysis_progress import (
    clear_cancelled as clear_cancelled_flag,
    is_cancelled as is_cancelled_flag,
    progress_path,
    read_file_progress,
    set_cancelled as set_cancelled_flag,
    write_file_progress,
)

# base_path = "data/images/"
# new_path = "data/ims/"
# for infile in os.listdir(base_path):
#     print ("file : " + infile)
#     read = cv2.imread(base_path + infile)
#     outfile = infile.split('.')[0] + '.jpg'
#     cv2.imwrite(new_path+outfile,read,[int(cv2.IMWRITE_JPEG_QUALITY), 200])


def tif_to_jpg(tif_path :Path, output_dir :Path) -> Path:
    filename = tif_path.stem
    read = cv2.imread(str(tif_path))
    temp =filename+ '.jpg'
    jpg_path = Path(output_dir / temp)
    cv2.imwrite(str(jpg_path), read,[int(cv2.IMWRITE_JPEG_QUALITY), 100])
    return jpg_path


logger = logging.getLogger(__name__)


def write_progress(key: str, phase: str, status: str | None = None, failure_summary: str = "") -> None:
    """Backward-compatible progress writer used by legacy views and tests."""

    write_file_progress(
        key,
        phase=phase,
        status=status,
        failure_summary=failure_summary,
    )


def read_progress(key: str) -> dict[str, object]:
    """Backward-compatible progress reader used by legacy callers."""

    return read_file_progress(key)


def is_cancelled(key: str) -> bool:
    """Backward-compatible cancel-flag check."""

    return is_cancelled_flag(key)


def set_cancelled(key: str) -> None:
    """Backward-compatible cancel-flag writer."""

    set_cancelled_flag(key)


def clear_cancelled(key: str) -> None:
    """Backward-compatible cancel-flag cleanup."""

    clear_cancelled_flag(key)


def prune_experiment_session_state(request, uuids) -> None:
    """Remove cancelled or deleted run UUIDs from session tracking."""

    normalized = {str(value) for value in uuids if str(value)}
    if not normalized:
        return

    changed = False
    for session_key in ("last_experiment_uuids", "transient_experiment_uuids"):
        existing = request.session.get(session_key, [])
        if not isinstance(existing, list):
            continue
        filtered = [str(value) for value in existing if str(value) not in normalized]
        if filtered != existing:
            request.session[session_key] = filtered
            changed = True

    if changed:
        request.session.modified = True


def sync_transient_run_session_state(request, uuids) -> None:
    """Align transient run session state with persisted segmented-image ownership."""

    normalized = {str(value) for value in uuids if str(value)}
    if not normalized:
        return

    current = {
        str(value)
        for value in request.session.get("transient_experiment_uuids", [])
        if str(value)
    }
    user_id = request.user.id if request.user.is_authenticated else get_guest_user()
    saved_by_current_user = {
        str(value)
        for value in SegmentedImage.objects.filter(
            UUID__in=normalized,
            user_id=user_id,
        ).values_list("UUID", flat=True)
    }

    next_transient = (current | (normalized - saved_by_current_user)) - saved_by_current_user
    if next_transient == current:
        return
    request.session["transient_experiment_uuids"] = sorted(next_transient)
    request.session.modified = True

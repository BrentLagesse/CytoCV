"""Shared helpers for frontend contract tests."""

from __future__ import annotations

import html
import json
import re
from contextlib import ExitStack, contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import override_settings
from unittest.mock import patch

from core.models import CellStatistics, DVLayerTifPreview, SegmentedImage, UploadedImage, get_guest_user


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CORE_STATIC_ROOT = PROJECT_ROOT / "core" / "static"
TEMPLATE_ROOT = PROJECT_ROOT / "templates"


def static_text(relative_path: str) -> str:
    return (CORE_STATIC_ROOT / relative_path).read_text(encoding="utf-8")


def response_text(response) -> str:
    return response.content.decode("utf-8")


def create_user(email: str = "frontend-contract@example.com", password: str = "TestPass123!"):
    return get_user_model().objects.create_user(email=email, password=password)


def login_user(testcase, email: str = "frontend-contract@example.com") -> Any:
    user = create_user(email=email)
    testcase.assertTrue(testcase.client.login(email=email, password="TestPass123!"))
    return user


def assert_in_order(testcase, content: str, *tokens: str) -> None:
    positions = []
    for token in tokens:
        testcase.assertIn(token, content)
        positions.append(content.index(token))
    testcase.assertEqual(positions, sorted(positions), f"Expected order: {tokens}")


def assert_no_duplicate_include(testcase, content: str, static_path: str) -> None:
    testcase.assertEqual(
        content.count(static_path),
        1,
        f"Expected exactly one include for {static_path}",
    )


def assert_no_inline_styles(testcase, content: str) -> None:
    lowered = content.lower()
    testcase.assertNotIn("<style", lowered)
    testcase.assertNotIn("style=", lowered)


def parse_json_script(content: str, script_id: str) -> Any:
    pattern = re.compile(
        rf"<script\b(?=[^>]*\bid=[\"']{re.escape(script_id)}[\"'])"
        rf"(?=[^>]*\btype=[\"']application/json[\"'])[^>]*>(.*?)</script>",
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(content)
    if not match:
        raise AssertionError(f"Missing JSON script #{script_id}")
    return json.loads(html.unescape(match.group(1).strip() or "null"))


def assert_json_script_keys(testcase, content: str, script_id: str, keys: tuple[str, ...]) -> Any:
    payload = parse_json_script(content, script_id)
    testcase.assertIsInstance(payload, dict)
    for key in keys:
        testcase.assertIn(key, payload, f"Missing key {key!r} in {script_id}")
    return payload


def create_display_file(
    *,
    uploaded_owner,
    segmented_owner_id=None,
    filename: str = "frontend_result",
    num_cells: int = 2,
) -> str:
    file_uuid = uuid4()
    segmented_owner_id = segmented_owner_id or uploaded_owner.id
    UploadedImage.objects.create(
        user=uploaded_owner,
        name=filename,
        uuid=file_uuid,
        file_location=f"{file_uuid}/{filename}.dv",
    )
    SegmentedImage.objects.create(
        user_id=segmented_owner_id,
        UUID=file_uuid,
        file_location=f"user_{file_uuid}/{filename}.png",
        ImagePath=f"{file_uuid}/output/{filename}_frame_0.png",
        CellPairPrefix=f"{file_uuid}/segmented/cell_",
        NumCells=num_cells,
    )
    return str(file_uuid)


def add_cell_stat(file_uuid: str, *, cell_id: int = 1, properties: dict | None = None) -> None:
    segmented = SegmentedImage.objects.get(UUID=file_uuid)
    stat_properties = {
        "signal_quantification_mode": "puncta_distance",
        "puncta_line_mode": "red_puncta",
        "nuclear_cell_pair_mode": "red_nucleus",
        "cen_dot_schema_version": 3,
        "puncta_distance_delta_x_px": 1.0,
        "puncta_distance_delta_y_px": 0.0,
        "red_contour_1_center_x_px": 10.0,
        "red_contour_1_center_y_px": 20.0,
        "green_contour_1_center_x_px": 30.0,
        "green_contour_1_center_y_px": 40.0,
    }
    if properties:
        stat_properties.update(properties)
    CellStatistics.objects.create(
        segmented_image=segmented,
        cell_id=cell_id,
        cell_type=(properties or {}).get("cell_type", "unknown"),
        puncta_distance=1.0,
        puncta_line_intensity=2.0,
        nucleus_intensity_sum=3.0,
        cell_pair_intensity_sum=4.0,
        blue_contour_size=9.0,
        distance_of_green_from_red_1=6.0,
        red_in_red_total_intensity_1=5.0,
        red_in_red_max_intensity_1=4.0,
        red_in_red_average_intensity_1=2.5,
        green_in_red_total_intensity_1=6.0,
        green_in_red_max_intensity_1=5.0,
        green_in_red_average_intensity_1=3.0,
        red_in_green_total_intensity_1=7.0,
        red_in_green_max_intensity_1=6.0,
        red_in_green_average_intensity_1=3.5,
        green_in_green_total_intensity_1=8.0,
        green_in_green_max_intensity_1=7.0,
        green_in_green_average_intensity_1=4.0,
        green_red_intensity_1=6.0 / 5.0,
        category_cen_dot=1,
        properties=stat_properties,
    )


def create_preprocess_file(user, *, filename: str = "frontend_preprocess") -> str:
    file_uuid = uuid4()
    uploaded = UploadedImage.objects.create(
        user=user,
        name=filename,
        uuid=file_uuid,
        file_location=f"{file_uuid}/{filename}.dv",
    )
    DVLayerTifPreview.objects.create(
        uploaded_image_uuid=uploaded,
        wavelength="DAPI",
        file_location=f"{file_uuid}/{filename}_preview.png",
    )
    return str(file_uuid)


def set_transient_uuids(client, uuids: list[str]) -> None:
    session = client.session
    session["transient_experiment_uuids"] = uuids
    session.save()


def guest_user_id():
    return get_guest_user()


@contextmanager
def temporary_media_root():
    with TemporaryDirectory() as temp_media:
        with ExitStack() as stack:
            stack.enter_context(override_settings(MEDIA_ROOT=temp_media))
            stack.enter_context(patch("accounts.views.profile.MEDIA_ROOT", temp_media))
            stack.enter_context(patch("core.config.MEDIA_ROOT", temp_media))
            stack.enter_context(patch("core.views.display.MEDIA_ROOT", temp_media))
            stack.enter_context(patch("core.views.pre_process.MEDIA_ROOT", temp_media))
            yield Path(temp_media)

import cv2
import math
import numpy as np
import logging
from dataclasses import dataclass
from scipy import ndimage as ndi
from skimage.feature import peak_local_max
from skimage.segmentation import find_boundaries, watershed

from core.contour_processing import get_largest
from core.image_processing import GrayImage
from core.services.green_dot_split import (
    DEFAULT_GREEN_DOT_SPLIT_MODE,
    normalize_green_dot_split_mode,
)

logger = logging.getLogger(__name__)

GREEN_DOT_SPLIT_PARAMS = {
    "balanced": {
        "min_original_area_px": 10,
        "min_peak_distance": 2,
        "min_peak_ratio": 0.25,
        "min_intensity_peak_ratio": 0.28,
        "min_second_peak_ratio": 0.32,
        "max_intensity_valley_ratio": 0.92,
        "max_distance_valley_ratio": 0.94,
        "min_defect_depth_px": 0.45,
        "min_relative_defect_depth": 0.07,
        "max_neck_width_ratio": 0.94,
        "min_chord_mask_fraction": 0.58,
        "max_single_dot_circularity": 0.90,
        "min_single_dot_solidity": 0.985,
        "max_single_dot_aspect_ratio": 1.18,
        "min_suspicious_aspect_ratio": 1.08,
        "max_suspicious_circularity": 0.84,
        "max_suspicious_solidity": 0.985,
        "min_split_circularity": 0.16,
        "min_split_solidity": 0.58,
        "min_split_area_px": 6,
        "min_child_area_fraction": 0.10,
        "min_combined_area_ratio": 0.66,
        "min_child_center_distance_px": 2.0,
        "max_child_aspect_ratio": 4.0,
        "min_child_peak_ratio": 0.25,
        "max_neck_alignment_cos": 0.88,
        "neck_cut_line_thickness": 1,
        "asymmetric_fallback_enabled": True,
        "asymmetric_min_peak_distance_px": 4.0,
        "asymmetric_min_second_peak_ratio": 0.32,
        "asymmetric_max_intensity_valley_ratio": 0.88,
        "asymmetric_min_intensity_drop_ratio": 0.10,
        "asymmetric_max_distance_saddle_ratio": 0.88,
        "asymmetric_min_peak_line_mask_fraction": 0.80,
        "asymmetric_min_single_defect_depth_px": 0.75,
        "asymmetric_max_saddle_to_defect_distance_px": 8.0,
        "asymmetric_min_child_area_fraction": 0.16,
        "asymmetric_min_child_mean_ratio": 0.16,
        "asymmetric_min_boundary_low_signal_fraction": 0.55,
        "asymmetric_max_boundary_saddle_distance_px": 6.0,
    },
    "aggressive": {
        "min_original_area_px": 8,
        "min_peak_distance": 1,
        "min_peak_ratio": 0.18,
        "min_intensity_peak_ratio": 0.20,
        "min_second_peak_ratio": 0.20,
        "max_intensity_valley_ratio": 0.96,
        "max_distance_valley_ratio": 0.97,
        "min_defect_depth_px": 0.25,
        "min_relative_defect_depth": 0.04,
        "max_neck_width_ratio": 1.00,
        "min_chord_mask_fraction": 0.45,
        "max_single_dot_circularity": 0.92,
        "min_single_dot_solidity": 0.99,
        "max_single_dot_aspect_ratio": 1.12,
        "min_suspicious_aspect_ratio": 1.04,
        "max_suspicious_circularity": 0.88,
        "max_suspicious_solidity": 0.99,
        "min_split_circularity": 0.10,
        "min_split_solidity": 0.45,
        "min_split_area_px": 4,
        "min_child_area_fraction": 0.06,
        "min_combined_area_ratio": 0.58,
        "min_child_center_distance_px": 1.0,
        "max_child_aspect_ratio": 5.5,
        "min_child_peak_ratio": 0.15,
        "max_neck_alignment_cos": 0.94,
        "neck_cut_line_thickness": 1,
        "asymmetric_fallback_enabled": True,
        "asymmetric_min_peak_distance_px": 2.0,
        "asymmetric_min_second_peak_ratio": 0.20,
        "asymmetric_max_intensity_valley_ratio": 0.94,
        "asymmetric_min_intensity_drop_ratio": 0.04,
        "asymmetric_max_distance_saddle_ratio": 0.94,
        "asymmetric_min_peak_line_mask_fraction": 0.60,
        "asymmetric_min_single_defect_depth_px": 0.35,
        "asymmetric_max_saddle_to_defect_distance_px": 10.0,
        "asymmetric_min_child_area_fraction": 0.08,
        "asymmetric_min_child_mean_ratio": 0.08,
        "asymmetric_min_boundary_low_signal_fraction": 0.40,
        "asymmetric_max_boundary_saddle_distance_px": 8.0,
    },
}

MAX_DEFECT_CANDIDATES = 8
MAX_PEAK_CANDIDATES = 8
PROFILE_SAMPLE_COUNT = 48
MIN_GREEN_CONTOUR_AREA = 8
GREEN_RING_KERNEL_SIZE = (11, 11)
GREEN_RING_P90_FLOOR = 1.0
GREEN_STRONG_PEAK_MAX_RATIO = 3.0
GREEN_STRONG_PEAK_P90_RATIO = 2.5


@dataclass(slots=True)
class _ContourShapeMetrics:
    contour: np.ndarray
    mask: np.ndarray
    area: float
    pixel_area: int
    perimeter: float
    circularity: float
    aspect_ratio: float
    solidity: float
    hull_area: float
    centroid: tuple[float, float]
    lobe_width_px: float
    deep_defect_count: int
    max_defect_depth_px: float


@dataclass(slots=True)
class _NeckCandidate:
    point_a: tuple[int, int]
    point_b: tuple[int, int]
    width_px: float
    neck_ratio: float
    depth_a_px: float
    depth_b_px: float
    chord_mask_fraction: float
    score: float


@dataclass(slots=True)
class _Peak:
    x: int
    y: int
    value: float

    @property
    def point(self) -> tuple[int, int]:
        return self.x, self.y


@dataclass(slots=True)
class _PeakPair:
    peak_a: _Peak
    peak_b: _Peak
    distance_px: float
    valley_value: float
    valley_ratio: float
    second_peak_ratio: float
    score: float


@dataclass(slots=True)
class _SingleDefectCandidate:
    point: tuple[int, int]
    depth_px: float
    score: float


@dataclass(slots=True)
class _SaddleMetrics:
    point: tuple[int, int]
    intensity_valley_ratio: float
    intensity_drop_ratio: float
    distance_saddle_ratio: float


@dataclass(slots=True)
class _AsymmetricSplitCandidate:
    peak_pair: _PeakPair
    saddle: _SaddleMetrics
    single_defect: _SingleDefectCandidate | None
    score: float


@dataclass(slots=True)
class _AggressiveSplitDecision:
    original_contour: np.ndarray
    output_contours: list[np.ndarray]
    accepted_split: bool


@dataclass(slots=True, frozen=True)
class _GreenContourFilterDecision:
    bbox: tuple[int, int, int, int]
    area: float
    closed_open_ratio: float | None
    inside_max: float | None
    inside_p90: float | None
    ring_p90: float | None
    max_over_ring_p90: float | None
    p90_over_ring_p90: float | None
    ring_pixel_count: int
    decision_reason: str


def _split_params(split_mode: str) -> dict:
    mode = normalize_green_dot_split_mode(split_mode)
    return GREEN_DOT_SPLIT_PARAMS[mode]


def contour_to_mask(contour: np.ndarray, shape: tuple[int, int] | tuple[int, int, int]) -> np.ndarray:
    """Return a filled binary mask for one contour in image coordinates."""

    height, width = int(shape[0]), int(shape[1])
    mask = np.zeros((height, width), dtype=np.uint8)
    if contour is not None and len(contour) >= 3:
        cv2.drawContours(mask, [contour], -1, 255, thickness=-1)
    return mask


def _dense_outer_contour(mask: np.ndarray) -> np.ndarray | None:
    contours, _ = cv2.findContours(mask.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contours:
        return None
    return max(contours, key=cv2.contourArea)


def _contour_center_from_mask(mask: np.ndarray) -> tuple[float, float]:
    moment = cv2.moments(mask, binaryImage=True)
    if moment["m00"] != 0:
        return (moment["m10"] / moment["m00"], moment["m01"] / moment["m00"])
    points = np.column_stack(np.nonzero(mask))
    if points.size == 0:
        return (0.0, 0.0)
    return (float(np.mean(points[:, 1])), float(np.mean(points[:, 0])))


def _contour_defects(contour: np.ndarray):
    if contour is None or len(contour) < 4:
        return None
    hull = cv2.convexHull(contour, returnPoints=False)
    if hull is None or len(hull) < 3:
        return None
    try:
        return cv2.convexityDefects(contour, hull)
    except cv2.error:
        try:
            sorted_hull = np.sort(hull.flatten()).reshape(-1, 1)
            return cv2.convexityDefects(contour, sorted_hull)
        except cv2.error:
            return None


def compute_contour_shape_metrics(
    contour: np.ndarray,
    image_shape: tuple[int, int] | tuple[int, int, int],
    *,
    min_defect_depth_px: float = 1.0,
) -> _ContourShapeMetrics | None:
    """Measure compactness, concavity, and lobe scale for one GFP contour."""

    mask = contour_to_mask(contour, image_shape)
    dense_contour = _dense_outer_contour(mask)
    if dense_contour is None or len(dense_contour) < 3:
        return None

    area = float(cv2.contourArea(dense_contour))
    pixel_area = int(np.count_nonzero(mask))
    perimeter = float(cv2.arcLength(dense_contour, True))
    circularity = 0.0
    if perimeter > 0:
        circularity = float((4.0 * math.pi * area) / (perimeter * perimeter))

    x, y, width, height = cv2.boundingRect(dense_contour)
    del x, y
    short_side = max(1, min(width, height))
    aspect_ratio = float(max(width, height) / short_side)

    hull = cv2.convexHull(dense_contour)
    hull_area = float(cv2.contourArea(hull)) if hull is not None and len(hull) >= 3 else 0.0
    solidity = float(area / hull_area) if hull_area > 0 else 1.0

    dist = ndi.distance_transform_edt(mask > 0)
    lobe_width_px = float(2.0 * dist.max()) if dist.size else 0.0

    defects = _contour_defects(dense_contour)
    deep_defect_count = 0
    max_defect_depth_px = 0.0
    if defects is not None:
        for _start, _end, _far, depth in defects[:, 0]:
            depth_px = float(depth) / 256.0
            max_defect_depth_px = max(max_defect_depth_px, depth_px)
            if depth_px >= float(min_defect_depth_px):
                deep_defect_count += 1

    return _ContourShapeMetrics(
        contour=dense_contour,
        mask=mask,
        area=area,
        pixel_area=pixel_area,
        perimeter=perimeter,
        circularity=circularity,
        aspect_ratio=aspect_ratio,
        solidity=solidity,
        hull_area=hull_area,
        centroid=_contour_center_from_mask(mask),
        lobe_width_px=lobe_width_px,
        deep_defect_count=deep_defect_count,
        max_defect_depth_px=max_defect_depth_px,
    )


def _sample_profile(
    image: np.ndarray,
    point_a: tuple[int, int],
    point_b: tuple[int, int],
    *,
    sample_count: int = PROFILE_SAMPLE_COUNT,
) -> np.ndarray:
    height, width = image.shape[:2]
    xs = np.linspace(float(point_a[0]), float(point_b[0]), int(sample_count))
    ys = np.linspace(float(point_a[1]), float(point_b[1]), int(sample_count))
    xs = np.clip(np.rint(xs).astype(np.int32), 0, width - 1)
    ys = np.clip(np.rint(ys).astype(np.int32), 0, height - 1)
    return image[ys, xs].astype(np.float32, copy=False)


def _sample_profile_with_points(
    image: np.ndarray,
    point_a: tuple[int, int],
    point_b: tuple[int, int],
    *,
    sample_count: int = PROFILE_SAMPLE_COUNT,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    height, width = image.shape[:2]
    xs = np.linspace(float(point_a[0]), float(point_b[0]), int(sample_count))
    ys = np.linspace(float(point_a[1]), float(point_b[1]), int(sample_count))
    xs = np.clip(np.rint(xs).astype(np.int32), 0, width - 1)
    ys = np.clip(np.rint(ys).astype(np.int32), 0, height - 1)
    return image[ys, xs].astype(np.float32, copy=False), xs, ys


def _chord_mask_fraction(
    mask: np.ndarray,
    point_a: tuple[int, int],
    point_b: tuple[int, int],
) -> float:
    profile = _sample_profile(mask, point_a, point_b)
    if profile.size <= 2:
        return 0.0
    interior = profile[1:-1]
    return float(np.count_nonzero(interior > 0) / max(len(interior), 1))


def find_convexity_defect_neck_candidates(
    contour: np.ndarray,
    mask: np.ndarray,
    params: dict,
) -> list[_NeckCandidate]:
    """Return paired concavity candidates that can form a neck chord."""

    dense_contour = _dense_outer_contour(mask)
    if dense_contour is None:
        return []
    defects = _contour_defects(dense_contour)
    if defects is None:
        return []

    min_depth = float(params["min_defect_depth_px"])
    candidates = []
    for _start, _end, far_idx, depth in defects[:, 0]:
        depth_px = float(depth) / 256.0
        if depth_px < min_depth:
            continue
        point = tuple(int(v) for v in dense_contour[int(far_idx)][0])
        candidates.append((point, depth_px))

    candidates.sort(key=lambda row: row[1], reverse=True)
    candidates = candidates[:MAX_DEFECT_CANDIDATES]
    if len(candidates) < 2:
        return []

    center = _contour_center_from_mask(mask)
    lobe_width = float(2.0 * ndi.distance_transform_edt(mask > 0).max())
    if lobe_width <= 0:
        return []

    necks: list[_NeckCandidate] = []
    for i in range(len(candidates)):
        for j in range(i + 1, len(candidates)):
            point_a, depth_a = candidates[i]
            point_b, depth_b = candidates[j]
            width_px = float(math.dist(point_a, point_b))
            if width_px <= 1.0:
                continue

            vec_a = np.array([point_a[0] - center[0], point_a[1] - center[1]], dtype=np.float32)
            vec_b = np.array([point_b[0] - center[0], point_b[1] - center[1]], dtype=np.float32)
            norm_product = float(np.linalg.norm(vec_a) * np.linalg.norm(vec_b))
            if norm_product <= 0:
                continue
            facing_cos = float(np.dot(vec_a, vec_b) / norm_product)
            if facing_cos > 0.35:
                continue

            chord_fraction = _chord_mask_fraction(mask, point_a, point_b)
            if chord_fraction < float(params["min_chord_mask_fraction"]):
                continue

            neck_ratio = float(width_px / max(lobe_width, 1e-6))
            if neck_ratio > float(params["max_neck_width_ratio"]):
                continue
            relative_depth = float(min(depth_a, depth_b) / max(lobe_width, 1e-6))
            if relative_depth < float(params["min_relative_defect_depth"]):
                continue

            depth_score = depth_a + depth_b
            ratio_score = max(0.0, 1.0 - neck_ratio) * 8.0
            score = depth_score + ratio_score + chord_fraction
            necks.append(
                _NeckCandidate(
                    point_a=point_a,
                    point_b=point_b,
                    width_px=width_px,
                    neck_ratio=neck_ratio,
                    depth_a_px=depth_a,
                    depth_b_px=depth_b,
                    chord_mask_fraction=chord_fraction,
                    score=score,
                )
            )

    necks.sort(key=lambda item: item.score, reverse=True)
    return necks


def _as_gray_float(image: np.ndarray | None) -> np.ndarray | None:
    if image is None:
        return None
    gray = np.asarray(image)
    if gray.ndim == 3:
        gray = cv2.cvtColor(gray, cv2.COLOR_RGB2GRAY)
    if gray.ndim != 2:
        return None
    return gray.astype(np.float32, copy=False)


def _smooth_gfp_image(gfp_image: np.ndarray | None) -> np.ndarray | None:
    gray = _as_gray_float(gfp_image)
    if gray is None or gray.size == 0:
        return None
    return cv2.GaussianBlur(gray, (3, 3), 0)


def find_intensity_peaks_in_contour(
    mask: np.ndarray,
    gfp_image: np.ndarray | None,
    params: dict,
) -> list[_Peak]:
    """Find bright GFP centers inside a contour mask."""

    smoothed = _smooth_gfp_image(gfp_image)
    if smoothed is None:
        return []
    inside = mask > 0
    if not np.any(inside):
        return []
    max_value = float(np.max(smoothed[inside]))
    if max_value <= 0:
        return []

    coords = peak_local_max(
        smoothed,
        min_distance=int(params["min_peak_distance"]),
        threshold_abs=max_value * float(params["min_intensity_peak_ratio"]),
        labels=inside,
        exclude_border=False,
    )
    peaks = [
        _Peak(x=int(x_coord), y=int(y_coord), value=float(smoothed[int(y_coord), int(x_coord)]))
        for y_coord, x_coord in coords
    ]
    peaks.sort(key=lambda peak: peak.value, reverse=True)
    return peaks[:MAX_PEAK_CANDIDATES]


def _find_distance_peaks_in_contour(mask: np.ndarray, params: dict) -> tuple[list[_Peak], np.ndarray]:
    dist = ndi.distance_transform_edt(mask > 0).astype(np.float32)
    max_value = float(dist.max())
    if max_value <= 0:
        return [], dist
    coords = peak_local_max(
        dist,
        min_distance=int(params["min_peak_distance"]),
        threshold_abs=max_value * float(params["min_peak_ratio"]),
        labels=mask > 0,
        exclude_border=False,
    )
    peaks = [
        _Peak(x=int(x_coord), y=int(y_coord), value=float(dist[int(y_coord), int(x_coord)]))
        for y_coord, x_coord in coords
    ]
    peaks.sort(key=lambda peak: peak.value, reverse=True)
    return peaks[:MAX_PEAK_CANDIDATES], dist


def _best_peak_pair(
    peaks: list[_Peak],
    profile_image: np.ndarray,
    params: dict,
    *,
    max_valley_ratio_key: str,
) -> _PeakPair | None:
    if len(peaks) < 2:
        return None
    best: _PeakPair | None = None
    min_distance = float(params["min_child_center_distance_px"])
    min_second_peak_ratio = float(params["min_second_peak_ratio"])
    max_valley_ratio = float(params[max_valley_ratio_key])

    for i in range(len(peaks)):
        for j in range(i + 1, len(peaks)):
            peak_a = peaks[i]
            peak_b = peaks[j]
            distance_px = float(math.dist(peak_a.point, peak_b.point))
            if distance_px < min_distance:
                continue
            high_peak = max(peak_a.value, peak_b.value)
            if high_peak <= 0:
                continue
            second_peak_ratio = float(min(peak_a.value, peak_b.value) / high_peak)
            if second_peak_ratio < min_second_peak_ratio:
                continue
            profile = _sample_profile(profile_image, peak_a.point, peak_b.point)
            if profile.size > 2:
                valley_value = float(np.min(profile[1:-1]))
            else:
                valley_value = float(min(peak_a.value, peak_b.value))
            valley_ratio = float(valley_value / max(min(peak_a.value, peak_b.value), 1e-6))
            distance_score = min(distance_px / 12.0, 1.5)
            valley_score = max(0.0, max_valley_ratio - valley_ratio) * 4.0
            score = second_peak_ratio + distance_score + valley_score
            pair = _PeakPair(
                peak_a=peak_a,
                peak_b=peak_b,
                distance_px=distance_px,
                valley_value=valley_value,
                valley_ratio=valley_ratio,
                second_peak_ratio=second_peak_ratio,
                score=score,
            )
            if best is None or pair.score > best.score:
                best = pair
    return best


def _markers_from_peak_pair(shape: tuple[int, int], peak_pair: _PeakPair) -> np.ndarray:
    markers = np.zeros(shape, dtype=np.int32)
    markers[int(peak_pair.peak_a.y), int(peak_pair.peak_a.x)] = 1
    markers[int(peak_pair.peak_b.y), int(peak_pair.peak_b.x)] = 2
    return markers


def _markers_from_neck(mask: np.ndarray, neck: _NeckCandidate, params: dict) -> np.ndarray | None:
    working = mask.copy()
    cv2.line(
        working,
        neck.point_a,
        neck.point_b,
        0,
        thickness=int(params["neck_cut_line_thickness"]),
        lineType=cv2.LINE_8,
    )
    num_labels, labels = cv2.connectedComponents((working > 0).astype(np.uint8), connectivity=8)
    regions = []
    for label in range(1, num_labels):
        region = labels == label
        area = int(np.count_nonzero(region))
        if area >= int(params["min_split_area_px"]):
            regions.append((area, region))
    regions.sort(key=lambda row: row[0], reverse=True)
    if len(regions) < 2:
        return None

    markers = np.zeros(mask.shape, dtype=np.int32)
    for marker_idx, (_area, region) in enumerate(regions[:2], start=1):
        dist = ndi.distance_transform_edt(region)
        y_coord, x_coord = np.unravel_index(int(np.argmax(dist)), dist.shape)
        markers[int(y_coord), int(x_coord)] = marker_idx
    return markers


def _split_score_image(mask: np.ndarray, gfp_image: np.ndarray | None) -> np.ndarray:
    dist = ndi.distance_transform_edt(mask > 0).astype(np.float32)
    if dist.max() > 0:
        dist = dist / float(dist.max())

    smoothed = _smooth_gfp_image(gfp_image)
    if smoothed is None:
        return dist
    inside = mask > 0
    if not np.any(inside):
        return dist
    values = smoothed[inside]
    min_value = float(values.min())
    max_value = float(values.max())
    if max_value <= min_value:
        return dist
    intensity = np.zeros(mask.shape, dtype=np.float32)
    intensity[inside] = (smoothed[inside] - min_value) / (max_value - min_value)
    return (0.65 * dist) + (0.35 * intensity)


def split_contour_with_watershed(
    mask: np.ndarray,
    gfp_image: np.ndarray | None,
    peak_pair: _PeakPair | None,
    params: dict,
    *,
    neck_candidate: _NeckCandidate | None = None,
) -> np.ndarray | None:
    """Split a contour mask into two marker-controlled watershed regions."""

    if peak_pair is not None:
        markers = _markers_from_peak_pair(mask.shape, peak_pair)
    elif neck_candidate is not None:
        markers = _markers_from_neck(mask, neck_candidate, params)
        if markers is None:
            return None
    else:
        return None

    score_image = _split_score_image(mask, gfp_image)
    labels = watershed(-score_image, markers, mask=mask > 0)
    if int(labels.max()) != 2:
        return None

    boundary = _internal_watershed_boundaries(labels)
    labels = labels.copy()
    labels[boundary] = 0
    return labels


def _split_contour_with_neck_chord(
    mask: np.ndarray,
    neck: _NeckCandidate,
    params: dict,
) -> np.ndarray | None:
    working = mask.copy()
    cv2.line(
        working,
        neck.point_a,
        neck.point_b,
        0,
        thickness=int(params["neck_cut_line_thickness"]),
        lineType=cv2.LINE_8,
    )
    num_labels, labels = cv2.connectedComponents((working > 0).astype(np.uint8), connectivity=8)
    regions = []
    for label in range(1, num_labels):
        region = labels == label
        area = int(np.count_nonzero(region))
        if area >= int(params["min_split_area_px"]):
            regions.append((area, label))
    regions.sort(key=lambda row: row[0], reverse=True)
    if len(regions) < 2:
        return None
    split_labels = np.zeros_like(labels, dtype=np.int32)
    for marker_idx, (_area, original_label) in enumerate(regions[:2], start=1):
        split_labels[labels == original_label] = marker_idx
    return split_labels


def _neck_chord_side_labels(
    mask: np.ndarray,
    neck: _NeckCandidate,
) -> np.ndarray:
    """Partition a contour mask by the two sides of the candidate neck chord."""

    labels = np.zeros(mask.shape, dtype=np.int32)
    ys, xs = np.nonzero(mask > 0)
    if xs.size == 0:
        return labels

    point_a = np.array(neck.point_a, dtype=np.float32)
    point_b = np.array(neck.point_b, dtype=np.float32)
    chord = point_b - point_a
    chord_norm = float(np.linalg.norm(chord))
    if chord_norm <= 0:
        return labels

    points = np.column_stack((xs, ys)).astype(np.float32, copy=False)
    relative = points - point_a
    signed = (chord[0] * relative[:, 1]) - (chord[1] * relative[:, 0])

    positive = signed > 1e-3
    negative = signed < -1e-3
    labels[ys[positive], xs[positive]] = 1
    labels[ys[negative], xs[negative]] = 2

    on_line = ~(positive | negative)
    if np.any(on_line):
        dist_a = np.sum((points[on_line] - point_a) ** 2, axis=1)
        dist_b = np.sum((points[on_line] - point_b) ** 2, axis=1)
        side_labels = np.where(dist_a <= dist_b, 1, 2)
        labels[ys[on_line], xs[on_line]] = side_labels

    return labels


def _markers_from_neck_geometry(
    mask: np.ndarray,
    neck: _NeckCandidate,
    params: dict,
) -> np.ndarray | None:
    """Seed each side of a neck chord without requiring the chord to disconnect the mask."""

    side_labels = _neck_chord_side_labels(mask, neck)
    dist = ndi.distance_transform_edt(mask > 0).astype(np.float32)
    markers = np.zeros(mask.shape, dtype=np.int32)
    min_area = int(params["min_split_area_px"])

    for label in (1, 2):
        region = side_labels == label
        if int(np.count_nonzero(region)) < min_area:
            return None
        region_dist = np.where(region, dist, -1.0)
        max_index = int(np.argmax(region_dist))
        if float(region_dist.flat[max_index]) <= 0:
            return None
        y_coord, x_coord = np.unravel_index(max_index, region_dist.shape)
        markers[int(y_coord), int(x_coord)] = label

    return markers if int(markers.max()) == 2 else None


def split_contour_with_geometry_first_watershed(
    mask: np.ndarray,
    gfp_image: np.ndarray | None,
    neck: _NeckCandidate,
    params: dict,
) -> np.ndarray | None:
    """Split a contour from neck geometry even when peak-based markers are unavailable."""

    markers = _markers_from_neck_geometry(mask, neck, params)
    if markers is None:
        return None

    score_image = _split_score_image(mask, gfp_image)
    labels = watershed(-score_image, markers, mask=mask > 0)
    if int(labels.max()) == 2:
        boundary = _internal_watershed_boundaries(labels)
        labels = labels.copy()
        labels[boundary] = 0
        return labels

    side_labels = _neck_chord_side_labels(mask, neck)
    return side_labels if int(side_labels.max()) == 2 else None


def _region_circularity(region: np.ndarray) -> float:
    contours, _ = cv2.findContours(
        (region.astype(np.uint8) * 255),
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )
    if not contours:
        return 0.0

    contour = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(contour)
    perimeter = cv2.arcLength(contour, True)
    if perimeter <= 0:
        return 0.0
    return float((4.0 * math.pi * area) / (perimeter * perimeter))


def _region_solidity(region: np.ndarray) -> float:
    contours, _ = cv2.findContours(
        (region.astype(np.uint8) * 255),
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )
    if not contours:
        return 0.0
    contour = max(contours, key=cv2.contourArea)
    area = float(cv2.contourArea(contour))
    hull = cv2.convexHull(contour)
    hull_area = float(cv2.contourArea(hull)) if hull is not None and len(hull) >= 3 else 0.0
    if hull_area <= 0:
        return 0.0
    return float(area / hull_area)


def _contour_from_region(region: np.ndarray) -> np.ndarray | None:
    contours, _ = cv2.findContours(
        (region.astype(np.uint8) * 255),
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )
    if not contours:
        return None
    return max(contours, key=cv2.contourArea)


def _label_at_point(labels: np.ndarray, point: tuple[int, int]) -> int:
    x_coord, y_coord = int(point[0]), int(point[1])
    height, width = labels.shape[:2]
    if x_coord < 0 or y_coord < 0 or x_coord >= width or y_coord >= height:
        return 0
    label = int(labels[y_coord, x_coord])
    if label:
        return label
    y0, y1 = max(0, y_coord - 1), min(height, y_coord + 2)
    x0, x1 = max(0, x_coord - 1), min(width, x_coord + 2)
    nearby = labels[y0:y1, x0:x1]
    nearby = nearby[nearby > 0]
    if nearby.size == 0:
        return 0
    values, counts = np.unique(nearby, return_counts=True)
    return int(values[int(np.argmax(counts))])


def validate_split_contours(
    original_mask: np.ndarray,
    split_labels: np.ndarray | None,
    gfp_image: np.ndarray | None,
    params: dict,
    *,
    peak_pair: _PeakPair | None = None,
    neck_candidate: _NeckCandidate | None = None,
    require_child_peak_ratio: bool = True,
) -> list[np.ndarray]:
    """Validate watershed/chord regions before replacing the original contour."""

    if split_labels is None or int(split_labels.max()) != 2:
        return []

    original_area = int(np.count_nonzero(original_mask))
    if original_area <= 0:
        return []

    gray = _as_gray_float(gfp_image)
    original_max = 0.0
    if gray is not None and gray.shape[:2] == original_mask.shape:
        original_values = gray[original_mask > 0]
        if original_values.size:
            original_max = float(np.max(original_values))

    child_contours: list[np.ndarray] = []
    child_areas: list[int] = []
    child_centers: list[tuple[float, float]] = []
    for label in (1, 2):
        region = split_labels == label
        area = int(np.count_nonzero(region))
        if area < int(params["min_split_area_px"]):
            return []
        contour = _contour_from_region(region)
        if contour is None or len(contour) < 3:
            return []
        if _region_circularity(region) < float(params["min_split_circularity"]):
            return []
        if _region_solidity(region) < float(params["min_split_solidity"]):
            return []
        _x, _y, width, height = cv2.boundingRect(contour)
        short_side = max(1, min(width, height))
        if (max(width, height) / short_side) > float(params["max_child_aspect_ratio"]):
            return []
        if (
            require_child_peak_ratio
            and original_max > 0
            and gray is not None
            and gray.shape[:2] == original_mask.shape
        ):
            child_values = gray[region]
            if child_values.size == 0:
                return []
            if float(np.max(child_values)) < original_max * float(params["min_child_peak_ratio"]):
                return []
        child_contours.append(contour)
        child_areas.append(area)
        child_centers.append(_contour_center_from_mask(region.astype(np.uint8) * 255))

    combined_area_ratio = float(sum(child_areas) / max(original_area, 1))
    if combined_area_ratio < float(params["min_combined_area_ratio"]):
        return []

    area_fraction = float(min(child_areas) / max(max(child_areas), 1))
    if area_fraction < float(params["min_child_area_fraction"]):
        return []

    center_distance = float(math.dist(child_centers[0], child_centers[1]))
    if center_distance < float(params["min_child_center_distance_px"]):
        return []

    if peak_pair is not None:
        label_a = _label_at_point(split_labels, peak_pair.peak_a.point)
        label_b = _label_at_point(split_labels, peak_pair.peak_b.point)
        if label_a == 0 or label_b == 0 or label_a == label_b:
            return []

    if neck_candidate is not None:
        center_vec = np.array(
            [
                child_centers[1][0] - child_centers[0][0],
                child_centers[1][1] - child_centers[0][1],
            ],
            dtype=np.float32,
        )
        neck_vec = np.array(
            [
                neck_candidate.point_b[0] - neck_candidate.point_a[0],
                neck_candidate.point_b[1] - neck_candidate.point_a[1],
            ],
            dtype=np.float32,
        )
        norm_product = float(np.linalg.norm(center_vec) * np.linalg.norm(neck_vec))
        if norm_product > 0:
            alignment = abs(float(np.dot(center_vec, neck_vec) / norm_product))
            if alignment > float(params["max_neck_alignment_cos"]):
                return []

    return child_contours


def _boundary_intersects_neck_chord(
    original_mask: np.ndarray,
    split_labels: np.ndarray,
    neck_candidate: _NeckCandidate,
) -> bool:
    boundary = _boundary_between_split_labels(original_mask, split_labels)
    if not np.any(boundary):
        return False

    chord_mask = np.zeros(original_mask.shape, dtype=np.uint8)
    cv2.line(
        chord_mask,
        neck_candidate.point_a,
        neck_candidate.point_b,
        1,
        thickness=1,
        lineType=cv2.LINE_8,
    )
    chord_region = ndi.binary_dilation(chord_mask.astype(bool), iterations=1)
    return bool(np.any(boundary & chord_region))


def validate_geometry_first_split(
    original_mask: np.ndarray,
    split_labels: np.ndarray | None,
    params: dict,
    neck_candidate: _NeckCandidate,
) -> list[np.ndarray]:
    """Validate an aggressive geometry-first split that does not rely on peak evidence."""

    child_contours = validate_split_contours(
        original_mask,
        split_labels,
        None,
        params,
        peak_pair=None,
        neck_candidate=neck_candidate,
        require_child_peak_ratio=False,
    )
    if len(child_contours) != 2 or split_labels is None:
        return []
    if not _boundary_intersects_neck_chord(original_mask, split_labels, neck_candidate):
        return []
    return child_contours


def _tighten_aggressive_split_children(
    child_contours: list[np.ndarray],
    tightening_image: np.ndarray | None,
    params: dict,
    *,
    peak_pair: _PeakPair | None = None,
) -> list[np.ndarray]:
    """Tighten accepted aggressive split children around their brighter cores."""

    if len(child_contours) != 2:
        return child_contours

    gray = _as_gray_float(tightening_image)
    if gray is None or gray.size == 0:
        return child_contours

    tightened_regions: list[np.ndarray] = []
    tightened_contours: list[np.ndarray] = []
    for child_contour in child_contours:
        child_mask = contour_to_mask(child_contour, gray.shape) > 0
        if not np.any(child_mask):
            return child_contours

        original_child_area = int(np.count_nonzero(child_mask))
        ys, xs = np.nonzero(child_mask)
        child_values = gray[ys, xs]
        if child_values.size == 0:
            return child_contours

        peak_index = int(np.argmax(child_values))
        peak_y = int(ys[peak_index])
        peak_x = int(xs[peak_index])
        child_peak = float(child_values[peak_index])
        percentile_70 = float(np.percentile(child_values, 70))
        tightening_threshold = max(child_peak * 0.55, percentile_70)

        core_mask = child_mask & (gray >= tightening_threshold)
        if not np.any(core_mask):
            return child_contours

        core_labels, _component_count = ndi.label(core_mask)
        peak_label = int(core_labels[peak_y, peak_x])
        if peak_label == 0:
            return child_contours

        peak_component = core_labels == peak_label
        tightened_region = ndi.binary_dilation(
            peak_component,
            structure=np.ones((3, 3), dtype=bool),
            iterations=1,
        )
        tightened_region &= child_mask

        tightened_area = int(np.count_nonzero(tightened_region))
        min_tightened_area = max(4, int(math.ceil(original_child_area * 0.25)))
        if tightened_area < min_tightened_area:
            return child_contours
        if not tightened_region[peak_y, peak_x]:
            return child_contours

        tightened_contour = _contour_from_region(tightened_region.astype(np.uint8))
        if tightened_contour is None or len(tightened_contour) < 3:
            return child_contours

        tightened_regions.append(tightened_region)
        tightened_contours.append(tightened_contour)

    if np.any(tightened_regions[0] & tightened_regions[1]):
        return child_contours

    if peak_pair is not None:
        tightened_labels = np.zeros(gray.shape, dtype=np.uint8)
        tightened_labels[tightened_regions[0]] = 1
        tightened_labels[tightened_regions[1]] = 2
        label_a = _label_at_point(tightened_labels, peak_pair.peak_a.point)
        label_b = _label_at_point(tightened_labels, peak_pair.peak_b.point)
        if label_a == 0 or label_b == 0 or label_a == label_b:
            return child_contours

    return tightened_contours


def _finalize_accepted_split_children(
    child_contours: list[np.ndarray],
    tightening_image: np.ndarray | None,
    params: dict,
    split_mode: str,
    *,
    peak_pair: _PeakPair | None = None,
) -> list[np.ndarray]:
    if split_mode != "aggressive" or len(child_contours) != 2:
        return child_contours
    return _tighten_aggressive_split_children(
        child_contours,
        tightening_image,
        params,
        peak_pair=peak_pair,
    )


def _internal_watershed_boundaries(labels: np.ndarray) -> np.ndarray:
    """Return boundary pixels between positive watershed regions only."""

    if labels.max() <= 1:
        return np.zeros(labels.shape, dtype=bool)

    positive_high = labels.max() + 1
    positive_min = ndi.minimum_filter(
        np.where(labels > 0, labels, positive_high),
        size=3,
        mode="constant",
        cval=positive_high,
    )
    positive_max = ndi.maximum_filter(
        np.where(labels > 0, labels, 0),
        size=3,
        mode="constant",
        cval=0,
    )
    has_positive_neighbor = (positive_min <= labels.max()) & (positive_max > 0)
    return (
        find_boundaries(labels, mode="thick")
        & (labels > 0)
        & has_positive_neighbor
        & (positive_min != positive_max)
    )


def _is_round_single_dot(metrics: _ContourShapeMetrics, params: dict) -> bool:
    return (
        metrics.circularity >= float(params["max_single_dot_circularity"])
        and metrics.solidity >= float(params["min_single_dot_solidity"])
        and metrics.aspect_ratio <= float(params["max_single_dot_aspect_ratio"])
        and metrics.deep_defect_count == 0
    )


def _shape_is_suspicious(metrics: _ContourShapeMetrics, params: dict) -> bool:
    return (
        metrics.aspect_ratio >= float(params["min_suspicious_aspect_ratio"])
        or metrics.circularity <= float(params["max_suspicious_circularity"])
        or metrics.solidity <= float(params["max_suspicious_solidity"])
        or metrics.deep_defect_count >= 2
    )


def _choose_split_peak_pair(
    intensity_pair: _PeakPair | None,
    distance_pair: _PeakPair | None,
    params: dict,
) -> _PeakPair | None:
    intensity_ok = (
        intensity_pair is not None
        and intensity_pair.valley_ratio <= float(params["max_intensity_valley_ratio"])
    )
    distance_ok = (
        distance_pair is not None
        and distance_pair.valley_ratio <= float(params["max_distance_valley_ratio"])
    )
    if intensity_ok and distance_ok:
        return intensity_pair if intensity_pair.score >= distance_pair.score else distance_pair
    if intensity_ok:
        return intensity_pair
    if distance_ok:
        return distance_pair
    return None


def find_single_concavity_candidates(
    contour: np.ndarray,
    mask: np.ndarray,
    params: dict,
) -> list[_SingleDefectCandidate]:
    """Return deep single-side concavities for asymmetric split confidence."""

    dense_contour = _dense_outer_contour(mask)
    if dense_contour is None:
        return []
    defects = _contour_defects(dense_contour)
    if defects is None:
        return []

    min_depth = float(params.get("asymmetric_min_single_defect_depth_px", 0.75))
    candidates: list[_SingleDefectCandidate] = []
    for _start, _end, far_idx, depth in defects[:, 0]:
        depth_px = float(depth) / 256.0
        if depth_px < min_depth:
            continue
        point = tuple(int(v) for v in dense_contour[int(far_idx)][0])
        candidates.append(
            _SingleDefectCandidate(
                point=point,
                depth_px=depth_px,
                score=depth_px,
            )
        )
    candidates.sort(key=lambda item: item.score, reverse=True)
    return candidates[:MAX_DEFECT_CANDIDATES]


def _central_profile_indices(length: int) -> np.ndarray:
    start = max(1, int(round(float(length) * 0.20)))
    stop = min(length - 1, int(round(float(length) * 0.80)))
    if stop <= start:
        return np.arange(1, max(length - 1, 1), dtype=np.int32)
    return np.arange(start, stop, dtype=np.int32)


def _single_defect_supports_saddle(
    defects: list[_SingleDefectCandidate],
    saddle_point: tuple[int, int],
    params: dict,
) -> _SingleDefectCandidate | None:
    max_distance = float(params.get("asymmetric_max_saddle_to_defect_distance_px", 8.0))
    supported = [
        defect
        for defect in defects
        if math.dist(defect.point, saddle_point) <= max_distance
    ]
    if not supported:
        return None
    supported.sort(key=lambda defect: defect.score, reverse=True)
    return supported[0]


def find_asymmetric_peak_saddle_candidate(
    mask: np.ndarray,
    gfp_image: np.ndarray,
    params: dict,
) -> _AsymmetricSplitCandidate | None:
    """Return two-peak/one-sided-saddle evidence for aggressive fallback."""

    smoothed = _smooth_gfp_image(gfp_image)
    if smoothed is None or smoothed.shape[:2] != mask.shape:
        return None

    peaks = find_intensity_peaks_in_contour(mask, smoothed, params)
    if len(peaks) < 2:
        return None

    distance_image = ndi.distance_transform_edt(mask > 0).astype(np.float32)
    if float(distance_image.max()) <= 0:
        return None

    contour = _dense_outer_contour(mask)
    defects = find_single_concavity_candidates(contour, mask, params) if contour is not None else []
    min_peak_distance = float(params.get("asymmetric_min_peak_distance_px", 4.0))
    min_second_ratio = float(params.get("asymmetric_min_second_peak_ratio", 0.32))
    max_intensity_valley_ratio = float(
        params.get("asymmetric_max_intensity_valley_ratio", 0.88)
    )
    min_intensity_drop_ratio = float(
        params.get("asymmetric_min_intensity_drop_ratio", 0.10)
    )
    max_distance_saddle_ratio = float(
        params.get("asymmetric_max_distance_saddle_ratio", 0.88)
    )
    min_line_mask_fraction = float(
        params.get("asymmetric_min_peak_line_mask_fraction", 0.80)
    )

    best: _AsymmetricSplitCandidate | None = None
    for i in range(len(peaks)):
        for j in range(i + 1, len(peaks)):
            peak_a = peaks[i]
            peak_b = peaks[j]
            peak_distance = float(math.dist(peak_a.point, peak_b.point))
            if peak_distance < min_peak_distance:
                continue

            high_peak = max(peak_a.value, peak_b.value)
            peak_floor = min(peak_a.value, peak_b.value)
            if high_peak <= 0 or peak_floor <= 0:
                continue
            second_peak_ratio = float(peak_floor / high_peak)
            if second_peak_ratio < min_second_ratio:
                continue

            line_mask_fraction = _chord_mask_fraction(mask, peak_a.point, peak_b.point)
            if line_mask_fraction < min_line_mask_fraction:
                continue

            intensity_profile, xs, ys = _sample_profile_with_points(
                smoothed,
                peak_a.point,
                peak_b.point,
            )
            distance_profile = _sample_profile(
                distance_image,
                peak_a.point,
                peak_b.point,
            )
            if intensity_profile.size < 4 or distance_profile.size != intensity_profile.size:
                continue

            central_indices = _central_profile_indices(int(intensity_profile.size))
            if central_indices.size == 0:
                continue

            peak_distance_floor = min(
                float(distance_image[int(peak_a.y), int(peak_a.x)]),
                float(distance_image[int(peak_b.y), int(peak_b.x)]),
            )
            if peak_distance_floor <= 0:
                continue

            intensity_ratios = intensity_profile[central_indices] / max(peak_floor, 1e-6)
            distance_ratios = distance_profile[central_indices] / max(peak_distance_floor, 1e-6)
            combined = (0.58 * intensity_ratios) + (0.42 * distance_ratios)
            profile_idx = int(central_indices[int(np.argmin(combined))])

            valley_value = float(intensity_profile[profile_idx])
            intensity_valley_ratio = float(valley_value / max(peak_floor, 1e-6))
            intensity_drop_ratio = float((peak_floor - valley_value) / max(high_peak, 1e-6))
            distance_saddle_ratio = float(
                distance_profile[profile_idx] / max(peak_distance_floor, 1e-6)
            )
            if intensity_valley_ratio > max_intensity_valley_ratio:
                continue
            if intensity_drop_ratio < min_intensity_drop_ratio:
                continue
            if distance_saddle_ratio > max_distance_saddle_ratio:
                continue

            saddle_point = (int(xs[profile_idx]), int(ys[profile_idx]))
            single_defect = _single_defect_supports_saddle(defects, saddle_point, params)
            peak_pair = _PeakPair(
                peak_a=peak_a,
                peak_b=peak_b,
                distance_px=peak_distance,
                valley_value=valley_value,
                valley_ratio=intensity_valley_ratio,
                second_peak_ratio=second_peak_ratio,
                score=0.0,
            )
            single_defect_bonus = 0.5 if single_defect is not None else 0.0

            score = (
                second_peak_ratio
                + min(peak_distance / 12.0, 1.5)
                + max(0.0, 1.0 - intensity_valley_ratio) * 3.0
                + max(0.0, 1.0 - distance_saddle_ratio) * 3.0
                + single_defect_bonus
            )
            peak_pair.score = score
            candidate = _AsymmetricSplitCandidate(
                peak_pair=peak_pair,
                saddle=_SaddleMetrics(
                    point=saddle_point,
                    intensity_valley_ratio=intensity_valley_ratio,
                    intensity_drop_ratio=intensity_drop_ratio,
                    distance_saddle_ratio=distance_saddle_ratio,
                ),
                single_defect=single_defect,
                score=score,
            )
            if best is None or candidate.score > best.score:
                best = candidate

    return best


def split_contour_with_asymmetric_watershed(
    mask: np.ndarray,
    gfp_image: np.ndarray,
    candidate: _AsymmetricSplitCandidate,
    params: dict,
) -> np.ndarray | None:
    """Split a one-sided-neck contour using two intensity peaks as markers."""

    return split_contour_with_watershed(
        mask,
        gfp_image,
        candidate.peak_pair,
        params,
    )


def _boundary_between_split_labels(
    original_mask: np.ndarray,
    split_labels: np.ndarray,
) -> np.ndarray:
    label_1_touch = ndi.binary_dilation(
        split_labels == 1,
        structure=np.ones((3, 3), dtype=bool),
        iterations=2,
    )
    label_2_touch = ndi.binary_dilation(
        split_labels == 2,
        structure=np.ones((3, 3), dtype=bool),
        iterations=2,
    )
    return (
        (original_mask > 0)
        & label_1_touch
        & label_2_touch
        & ((split_labels == 0) | find_boundaries(split_labels, mode="thick"))
    )


def _boundary_reaches_saddle(
    boundary: np.ndarray,
    saddle_point: tuple[int, int],
    params: dict,
    peak_distance: float,
) -> bool:
    points = np.column_stack(np.nonzero(boundary))
    if points.size == 0:
        return False
    saddle_yx = np.array([saddle_point[1], saddle_point[0]], dtype=np.float32)
    distances = np.linalg.norm(points.astype(np.float32) - saddle_yx, axis=1)
    max_distance = max(
        float(params.get("asymmetric_max_boundary_saddle_distance_px", 6.0)),
        peak_distance * 0.25,
    )
    return bool(float(np.min(distances)) <= max_distance)


def validate_asymmetric_split(
    original_mask: np.ndarray,
    split_labels: np.ndarray | None,
    gfp_image: np.ndarray,
    candidate: _AsymmetricSplitCandidate,
    params: dict,
) -> list[np.ndarray]:
    """Apply extra saddle and child-intensity gates to fallback watershed."""

    child_contours = validate_split_contours(
        original_mask,
        split_labels,
        gfp_image,
        params,
        peak_pair=candidate.peak_pair,
        neck_candidate=None,
    )
    if len(child_contours) != 2 or split_labels is None:
        return []

    gray = _as_gray_float(gfp_image)
    if gray is None or gray.shape[:2] != original_mask.shape:
        return []
    original_values = gray[original_mask > 0]
    if original_values.size == 0:
        return []
    original_max = float(np.max(original_values))
    if original_max <= 0:
        return []

    child_areas: list[int] = []
    child_centers: list[tuple[float, float]] = []
    for label in (1, 2):
        region = split_labels == label
        child_values = gray[region]
        if child_values.size == 0:
            return []
        if float(np.mean(child_values)) < original_max * float(
            params.get("asymmetric_min_child_mean_ratio", 0.20)
        ):
            return []
        child_areas.append(int(np.count_nonzero(region)))
        child_centers.append(_contour_center_from_mask(region.astype(np.uint8) * 255))

    if min(child_areas) / max(max(child_areas), 1) < float(
        params.get("asymmetric_min_child_area_fraction", 0.16)
    ):
        return []
    if math.dist(child_centers[0], child_centers[1]) < float(
        params.get("asymmetric_min_peak_distance_px", 4.0)
    ):
        return []

    boundary = _boundary_between_split_labels(original_mask, split_labels)
    if not np.any(boundary):
        return []
    if not _boundary_reaches_saddle(
        boundary,
        candidate.saddle.point,
        params,
        candidate.peak_pair.distance_px,
    ):
        return []

    smoothed = _smooth_gfp_image(gfp_image)
    if smoothed is None or smoothed.shape[:2] != original_mask.shape:
        return []
    distance_image = ndi.distance_transform_edt(original_mask > 0).astype(np.float32)
    peak_floor = min(candidate.peak_pair.peak_a.value, candidate.peak_pair.peak_b.value)
    peak_distance_floor = min(
        float(distance_image[candidate.peak_pair.peak_a.y, candidate.peak_pair.peak_a.x]),
        float(distance_image[candidate.peak_pair.peak_b.y, candidate.peak_pair.peak_b.x]),
    )
    if peak_floor <= 0 or peak_distance_floor <= 0:
        return []

    boundary_intensity_ok = smoothed[boundary] <= (
        peak_floor * float(params.get("asymmetric_max_intensity_valley_ratio", 0.88))
    )
    boundary_distance_ok = distance_image[boundary] <= (
        peak_distance_floor * float(params.get("asymmetric_max_distance_saddle_ratio", 0.88))
    )
    low_signal_fraction = float(
        np.count_nonzero(boundary_intensity_ok | boundary_distance_ok)
        / max(np.count_nonzero(boundary), 1)
    )
    if low_signal_fraction < float(
        params.get("asymmetric_min_boundary_low_signal_fraction", 0.55)
    ):
        return []

    return child_contours


def split_asymmetric_gfp_contour_if_needed(
    metrics: _ContourShapeMetrics,
    gfp_image: np.ndarray,
    params: dict,
    *,
    tightening_image: np.ndarray | None = None,
    has_paired_neck: bool = False,
    split_mode: str = DEFAULT_GREEN_DOT_SPLIT_MODE,
    debug: bool = False,
) -> list[np.ndarray]:
    if not bool(params.get("asymmetric_fallback_enabled", False)):
        return []
    if _is_round_single_dot(metrics, params):
        if debug:
            logger.debug("Green asymmetric split rejected: contour is compact and round")
        return []

    candidate = find_asymmetric_peak_saddle_candidate(metrics.mask, gfp_image, params)
    if candidate is None:
        if debug:
            logger.debug("Green asymmetric split rejected: no two-peak saddle")
        return []

    split_labels = split_contour_with_asymmetric_watershed(
        metrics.mask,
        gfp_image,
        candidate,
        params,
    )
    child_contours = validate_asymmetric_split(
        metrics.mask,
        split_labels,
        gfp_image,
        candidate,
        params,
    )
    if len(child_contours) == 2:
        return _finalize_accepted_split_children(
            child_contours,
            tightening_image,
            params,
            split_mode,
            peak_pair=candidate.peak_pair,
        )

    if debug:
        logger.debug("Green asymmetric split rejected: watershed failed validation")
    return []


def split_necked_gfp_contour_if_needed(
    contour: np.ndarray,
    gfp_image: np.ndarray,
    config: dict | str | None = None,
) -> list[np.ndarray]:
    """Return one original contour or two child contours for a necked GFP blob.

    The splitter is intentionally gated by the existing contour outline. It only
    attempts a split when the blob has paired concave defects forming a narrow
    waist, plus either two lobe peaks or strong peanut/dumbbell shape metrics.
    """

    if contour is None or len(contour) < 3:
        return []

    if isinstance(config, str):
        split_mode = config
        debug = False
        tightening_image = None
    else:
        config_payload = dict(config or {})
        split_mode = config_payload.get("mode", DEFAULT_GREEN_DOT_SPLIT_MODE)
        debug = bool(config_payload.get("debug", False))
        tightening_image = config_payload.get("tightening_image")
    split_mode = normalize_green_dot_split_mode(split_mode)

    params = _split_params(split_mode)
    tightening_gray = _as_gray_float(tightening_image)
    if tightening_gray is None or tightening_gray.shape[:2] != gfp_image.shape[:2]:
        tightening_gray = _as_gray_float(gfp_image)
    metrics = compute_contour_shape_metrics(
        contour,
        gfp_image.shape,
        min_defect_depth_px=float(params["min_defect_depth_px"]),
    )
    if metrics is None:
        return [contour]
    if metrics.pixel_area < int(params["min_original_area_px"]):
        return [contour]

    neck_candidates = find_convexity_defect_neck_candidates(
        metrics.contour,
        metrics.mask,
        params,
    )
    neck = neck_candidates[0] if neck_candidates else None

    intensity_peaks = find_intensity_peaks_in_contour(metrics.mask, gfp_image, params)
    smoothed = _smooth_gfp_image(gfp_image)
    intensity_pair = None
    if smoothed is not None:
        intensity_pair = _best_peak_pair(
            intensity_peaks,
            smoothed,
            params,
            max_valley_ratio_key="max_intensity_valley_ratio",
        )

    distance_peaks, distance_image = _find_distance_peaks_in_contour(metrics.mask, params)
    distance_pair = _best_peak_pair(
        distance_peaks,
        distance_image,
        params,
        max_valley_ratio_key="max_distance_valley_ratio",
    )

    def try_asymmetric_fallback() -> list[np.ndarray]:
        return split_asymmetric_gfp_contour_if_needed(
            metrics,
            gfp_image,
            params,
            tightening_image=tightening_gray,
            has_paired_neck=neck is not None,
            split_mode=split_mode,
            debug=debug,
        )

    if neck is None:
        child_contours = try_asymmetric_fallback()
        if len(child_contours) == 2:
            return child_contours
        if debug:
            logger.debug("Green neck split rejected: no paired concavity")
        return [contour]
    if _is_round_single_dot(metrics, params):
        if debug:
            logger.debug("Green neck split rejected: contour is compact and round")
        return [contour]

    shape_suspicious = _shape_is_suspicious(metrics, params)
    split_peak_pair = _choose_split_peak_pair(intensity_pair, distance_pair, params)
    if (
        split_mode == "aggressive"
        and split_peak_pair is None
        and metrics.aspect_ratio >= 2.0
        and metrics.solidity >= 0.94
        and (
            metrics.max_defect_depth_px < 1.0
            or neck.neck_ratio > 0.80
        )
    ):
        if debug:
            logger.debug(
                "Green neck split rejected: smooth convex contour lacks peak-supported or usable neck-supported split evidence"
            )
        return [contour]
    has_peak_evidence = split_peak_pair is not None
    has_geometry_evidence = shape_suspicious and metrics.deep_defect_count >= 2
    if not (has_peak_evidence or has_geometry_evidence):
        child_contours = try_asymmetric_fallback()
        if len(child_contours) == 2:
            return child_contours
        if debug:
            logger.debug("Green neck split rejected: no two-lobe evidence")
        return [contour]

    # Watershed is preferred because it lets the split follow the intensity and
    # distance ridge while staying constrained to the original merged contour.
    split_labels = split_contour_with_watershed(
        metrics.mask,
        gfp_image,
        split_peak_pair,
        params,
        neck_candidate=neck,
    )
    child_contours = validate_split_contours(
        metrics.mask,
        split_labels,
        gfp_image,
        params,
        peak_pair=split_peak_pair,
        neck_candidate=neck,
    )
    if len(child_contours) == 2:
        return _finalize_accepted_split_children(
            child_contours,
            tightening_gray,
            params,
            split_mode,
            peak_pair=split_peak_pair,
        )

    # If the watershed markers do not pass validation, a strong paired-defect
    # neck can still be separated by the direct chord between the concave points.
    chord_labels = _split_contour_with_neck_chord(metrics.mask, neck, params)
    child_contours = validate_split_contours(
        metrics.mask,
        chord_labels,
        gfp_image,
        params,
        peak_pair=None,
        neck_candidate=neck,
    )
    if len(child_contours) == 2:
        return _finalize_accepted_split_children(
            child_contours,
            tightening_gray,
            params,
            split_mode,
            peak_pair=split_peak_pair,
        )

    if (
        split_mode == "aggressive"
        and metrics.max_defect_depth_px >= 1.0
        and neck.neck_ratio <= 0.80
        and (
            split_peak_pair is not None
            or (
                shape_suspicious
                and metrics.aspect_ratio >= 1.35
            )
        )
    ):
        geometry_labels = split_contour_with_geometry_first_watershed(
            metrics.mask,
            gfp_image,
            neck,
            params,
        )
        child_contours = validate_geometry_first_split(
            metrics.mask,
            geometry_labels,
            params,
            neck,
        )
        if len(child_contours) == 2:
            return _finalize_accepted_split_children(
                child_contours,
                tightening_gray,
                params,
                split_mode,
                peak_pair=split_peak_pair,
            )

    child_contours = try_asymmetric_fallback()
    if len(child_contours) == 2:
        return child_contours

    if debug:
        logger.debug("Green neck split rejected: candidate split failed validation")
    return [contour]


def postprocess_gfp_contours_for_neck_splits(
    contours: list[np.ndarray] | tuple[np.ndarray, ...],
    gfp_image: np.ndarray,
    config: dict | str | None = None,
) -> list[np.ndarray]:
    """Replace merged necked GFP contours with two validated child contours."""

    processed: list[np.ndarray] = []
    for contour in contours or []:
        split_contours = split_necked_gfp_contour_if_needed(contour, gfp_image, config)
        processed.extend(split_contours if split_contours else [contour])
    return processed


def _aggressive_split_decision_for_contour(
    contour: np.ndarray,
    gfp_image: np.ndarray,
    config: dict | str | None = None,
) -> _AggressiveSplitDecision:
    """Return the aggressive split result for one contour without filtering."""

    split_contours = split_necked_gfp_contour_if_needed(contour, gfp_image, config)
    if len(split_contours) == 2:
        return _AggressiveSplitDecision(
            original_contour=contour,
            output_contours=split_contours,
            accepted_split=True,
        )
    return _AggressiveSplitDecision(
        original_contour=contour,
        output_contours=split_contours if split_contours else [contour],
        accepted_split=False,
    )


def _postprocess_and_filter_aggressive_green_contours(
    contours: list[np.ndarray] | tuple[np.ndarray, ...],
    gfp_image: np.ndarray,
    config: dict | str | None = None,
) -> list[np.ndarray]:
    """Preserve aggressive splits atomically through the legacy contour filter."""

    processed: list[np.ndarray] = []
    for contour in contours or []:
        decision = _aggressive_split_decision_for_contour(contour, gfp_image, config)
        if decision.accepted_split:
            filtered_children, _ = _filter_green_contours_with_image(
                decision.output_contours,
                gfp_image,
            )
            if len(filtered_children) == 2:
                processed.extend(filtered_children)
            else:
                # If the legacy filter collapses an accepted split, keep the
                # original merged contour instead of returning one child.
                processed.append(decision.original_contour)
            continue
        filtered_contours, _ = _filter_green_contours_with_image(
            decision.output_contours,
            gfp_image,
        )
        processed.extend(filtered_contours)
    return processed


def _split_merged_green_contours(
    thresh_green: np.ndarray,
    split_mode: str = DEFAULT_GREEN_DOT_SPLIT_MODE,
) -> np.ndarray:
    """Backward-compatible mask wrapper for the contour postprocessor."""

    contours, _ = cv2.findContours(
        (thresh_green > 0).astype(np.uint8) * 255,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )
    if not contours:
        return thresh_green
    processed = postprocess_gfp_contours_for_neck_splits(
        contours,
        thresh_green,
        {"mode": split_mode},
    )
    split_mask = np.zeros_like(thresh_green, dtype=np.uint8)
    for contour in processed:
        cv2.drawContours(split_mask, [contour], -1, 255, thickness=-1)
    return split_mask


def find_contours(
    images: GrayImage,
    green_contour_filter_enabled: bool = False,
    alternate_red_detection: bool = False,
    green_dot_split_enabled: bool = True,
    green_dot_split_mode: str = DEFAULT_GREEN_DOT_SPLIT_MODE,
):
    """
    Find red dot contours, blue nucleus contours, and green signal contours.
    """

    gray_red_3 = images.get_image("gray_red_3")
    gray_red = images.get_image("gray_red")
    gray_blue_3 = images.get_image("gray_blue_3")
    gray_blue = images.get_image("gray_blue")
    gray_green = images.get_image("green")
    gray_green_no_bg = images.get_image("green_no_bg")
    green_dot_split_mode = normalize_green_dot_split_mode(green_dot_split_mode)

    dot_contours = []
    contours = []
    contours_red = []
    best_contours = []
    best_contours_red = []

    if not alternate_red_detection:
        if gray_red_3 is not None:
            low_val, _ = cv2.threshold(
                gray_red_3,
                0.65,
                255,
                cv2.THRESH_BINARY + cv2.THRESH_OTSU,
            )
            _, bright_thresh = cv2.threshold(
                gray_red_3,
                low_val + 11,
                255,
                cv2.THRESH_BINARY,
            )
            dot_contours, _ = cv2.findContours(
                bright_thresh,
                cv2.RETR_LIST,
                cv2.CHAIN_APPROX_SIMPLE,
            )
            dot_contours = [cnt for cnt in dot_contours if cv2.contourArea(cnt) < 100]

        thresh_red = None
        thresh = None
        if gray_red_3 is not None and gray_red is not None:
            thresh_red = cv2.Canny(gray_red_3, 50, 150)
            thresh = cv2.Canny(gray_red, 50, 150)

            if np.max(thresh) == 0:
                _, thresh = cv2.threshold(
                    gray_red,
                    0,
                    1,
                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C | cv2.THRESH_OTSU,
                )

            if np.max(thresh_red) == 0:
                _, thresh_red = cv2.threshold(
                    gray_red_3,
                    0,
                    1,
                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C | cv2.THRESH_OTSU,
                )

            contours, _ = cv2.findContours(thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
            contours_red, _ = cv2.findContours(
                thresh_red,
                cv2.RETR_LIST,
                cv2.CHAIN_APPROX_SIMPLE,
            )
            best_contours = get_largest(contours)
            best_contours_red = get_largest(contours_red)
    else: # Alternate mode
        # Flag for trying to connect red signals
        bridge_red = False

        # Find the number of blue contours
        if gray_blue is not None:
            gray_blue_blur = cv2.GaussianBlur(gray_blue, (9, 9), 0)
            _, thresh_blue_blur = cv2.threshold(
                gray_blue_blur,
                40,
                255,
                cv2.THRESH_BINARY,
            )
            blue_blur_contours, _ = cv2.findContours(
                thresh_blue_blur,
                cv2.RETR_EXTERNAL,
                cv2.CHAIN_APPROX_SIMPLE,
            )
            blue_blur_contours = [cnt for cnt in blue_blur_contours if cv2.contourArea(cnt) >= 150]
            bridge_red = len(blue_blur_contours) < 2

        if gray_red_3 is not None:
            gray_red_3 = cv2.GaussianBlur(gray_red_3, (9, 9), 0)
            _, bright_thresh = cv2.threshold(
                gray_red_3,
                5,
                255,
                cv2.THRESH_BINARY,
            )
            # NOTE: Adaptive doesn't work well when there are strong signals
            dot_contours, _ = cv2.findContours(
                bright_thresh,
                cv2.RETR_EXTERNAL,
                cv2.CHAIN_APPROX_SIMPLE,
            )
        if gray_red_3 is not None and gray_red is not None:
            _, thresh = cv2.threshold(
                gray_red,
                5,
                255,
                cv2.THRESH_BINARY,
            )
            thresh_red = bright_thresh
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            contours_red, _ = cv2.findContours(
                thresh_red,
                cv2.RETR_EXTERNAL,
                cv2.CHAIN_APPROX_SIMPLE,
            )
            best_contours = get_largest(contours)
            best_contours_red = get_largest(contours_red)

            # Checking whether we need to try to connect red contours
            if bridge_red and (len(best_contours) > 1 or len(best_contours_red) > 1):
                # Try lower thresholds to connect red contours
                # NOTE: Other approaches have been tried, such as morphological ops and geometric bridging.
                # However, they were decided against due to basically making up the data.
                if gray_red_3 is not None and gray_red is not None:
                    _, bright_thresh = cv2.threshold(
                        gray_red_3,
                        4,
                        255,
                        cv2.THRESH_BINARY,
                    )
                    dot_contours, _ = cv2.findContours(
                        bright_thresh,
                        cv2.RETR_EXTERNAL,
                        cv2.CHAIN_APPROX_SIMPLE,
                    )
                    _, thresh = cv2.threshold(
                        gray_red,
                        4,
                        255,
                        cv2.THRESH_BINARY,
                    )
                    thresh_red = bright_thresh
                    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    contours_red, _ = cv2.findContours(
                        thresh_red,
                        cv2.RETR_EXTERNAL,
                        cv2.CHAIN_APPROX_SIMPLE,
                    )
                    best_contours = get_largest(contours)
                    best_contours_red = get_largest(contours_red)


    contours_blue = []
    contours_blue_3 = []
    best_contours_blue = []
    best_contours_blue_3 = []
    if gray_blue_3 is not None and gray_blue is not None:
        low_val, _ = cv2.threshold(
            gray_blue,
            0.65,
            255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU,
        )
        _, thresh_blue = cv2.threshold(
            gray_blue,
            low_val + 20,
            255,
            cv2.THRESH_BINARY,
        )

        low_val, _ = cv2.threshold(
            gray_blue_3,
            0.65,
            255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU,
        )
        _, thresh_blue_3 = cv2.threshold(
            gray_blue_3,
            low_val + 17,
            255,
            cv2.THRESH_BINARY,
        )

        contours_blue, _ = cv2.findContours(
            thresh_blue,
            cv2.RETR_LIST,
            cv2.CHAIN_APPROX_SIMPLE,
        )
        contours_blue_3, _ = cv2.findContours(
            thresh_blue_3,
            cv2.RETR_LIST,
            cv2.CHAIN_APPROX_SIMPLE,
        )
        best_contours_blue = get_largest(contours_blue)
        best_contours_blue_3 = get_largest(contours_blue_3) if contours_blue_3 else []

    contours_green = []
    if gray_green is not None:
        low_val, _ = cv2.threshold(
            gray_green,
            0.65,
            255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU,
        )
        _, thresh_green = cv2.threshold(
            gray_green,
            low_val + 13,
            255,
            cv2.THRESH_BINARY,
        )
        kernel = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
        thresh_green = cv2.morphologyEx(thresh_green, cv2.MORPH_CLOSE, kernel)
        contours_green, _ = cv2.findContours(
            thresh_green,
            cv2.RETR_LIST,
            cv2.CHAIN_APPROX_SIMPLE,
        )
        split_config = {
            "mode": green_dot_split_mode,
            "tightening_image": (
                gray_green_no_bg if gray_green_no_bg is not None else gray_green
            ),
        }
        if green_dot_split_enabled and green_contour_filter_enabled and green_dot_split_mode == "aggressive":
            contours_green = _postprocess_and_filter_aggressive_green_contours(
                contours_green,
                gray_green,
                split_config,
            )
        elif green_dot_split_enabled:
            contours_green = postprocess_gfp_contours_for_neck_splits(
                contours_green,
                gray_green,
                split_config,
            )
            if green_contour_filter_enabled:
                contours_green, _ = _filter_green_contours_with_image(
                    contours_green,
                    gray_green,
                )
        elif green_contour_filter_enabled:
            contours_green, _ = _filter_green_contours_with_image(
                contours_green,
                gray_green,
            )

    return {
        "best_contours": best_contours,
        "best_contours_red": best_contours_red,
        "contours": contours,
        "contours_red": contours_red,
        "contours_blue": contours_blue,
        "contours_blue_3": contours_blue_3,
        "best_contours_blue": best_contours_blue,
        "best_contours_blue_3": best_contours_blue_3,
        "dot_contours": dot_contours,
        "contours_green": contours_green,
    }


def merge_contour(bestContours, contours):
    """
    This function merges contours into a single contour.
    :param bestContours: List of best contours
    :param contours: List of contours
    :return: bestContours merged list
    """
    best_contour = None
    if len(bestContours) == 2:
        c1 = contours[bestContours[0]]
        c2 = contours[bestContours[1]]
        MERGE_CLOSEST = True
        if MERGE_CLOSEST:
            smallest_distance = 999999999
            second_smallest_distance = 999999999
            smallest_pair = (-1, -1)

            for pt1 in c1:
                for i, pt2 in enumerate(c2):
                    d = math.sqrt((pt1[0][0] - pt2[0][0]) ** 2 + (pt1[0][1] - pt2[0][1]) ** 2)
                    if d < smallest_distance:
                        second_smallest_distance = smallest_distance
                        second_smallest_pair = smallest_pair
                        smallest_distance = d
                        smallest_pair = (pt1, pt2, i)
                    elif d < second_smallest_distance:
                        second_smallest_distance = d
                        second_smallest_pair = (pt1, pt2, i)

            best_contour = []
            for pt1 in c1:
                best_contour.append(pt1)
                if pt1[0].tolist() != smallest_pair[0][0].tolist():
                    continue
                start_loc = smallest_pair[2]
                finish_loc = start_loc - 1
                if start_loc == 0:
                    finish_loc = len(c2) - 1
                current_loc = start_loc
                while current_loc != finish_loc:
                    best_contour.append(c2[current_loc])
                    current_loc += 1
                    if current_loc >= len(c2):
                        current_loc = 0
                best_contour.append(c2[finish_loc])

            best_contour = np.array(best_contour).reshape((-1, 1, 2)).astype(np.int32)

    if len(bestContours) == 1:
        best_contour = contours[bestContours[0]]

    if len(bestContours) == 1:
        logger.debug("Only one contour found while merging contour candidates")
    return best_contour


def _closed_open_ratio(contour: np.ndarray) -> float | None:
    closed = cv2.arcLength(contour, True)
    opened = cv2.arcLength(contour, False)
    if opened <= 0:
        return None
    return float(closed / opened)


def _log_green_contour_filter_decisions(
    decisions: list[_GreenContourFilterDecision],
) -> None:
    for decision in decisions:
        logger.debug(
            "Green contour filter decision: bbox=%s area=%.3f "
            "closed_open_ratio=%s inside_max=%s inside_p90=%s ring_p90=%s "
            "max_over_ring_p90=%s p90_over_ring_p90=%s ring_pixel_count=%d "
            "decision_reason=%s",
            decision.bbox,
            decision.area,
            decision.closed_open_ratio,
            decision.inside_max,
            decision.inside_p90,
            decision.ring_p90,
            decision.max_over_ring_p90,
            decision.p90_over_ring_p90,
            decision.ring_pixel_count,
            decision.decision_reason,
        )


def _filter_green_contours_with_image(
    contours: list[np.ndarray] | tuple[np.ndarray, ...],
    gray_green: np.ndarray,
) -> tuple[list[np.ndarray], list[_GreenContourFilterDecision]]:
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, GREEN_RING_KERNEL_SIZE)
    accepted: list[np.ndarray] = []
    decisions: list[_GreenContourFilterDecision] = []

    for contour in contours or []:
        area = float(cv2.contourArea(contour))
        bbox = tuple(int(value) for value in cv2.boundingRect(contour))

        if area < MIN_GREEN_CONTOUR_AREA:
            decisions.append(
                _GreenContourFilterDecision(
                    bbox=bbox,
                    area=area,
                    closed_open_ratio=None,
                    inside_max=None,
                    inside_p90=None,
                    ring_p90=None,
                    max_over_ring_p90=None,
                    p90_over_ring_p90=None,
                    ring_pixel_count=0,
                    decision_reason="rejected_area",
                )
            )
            continue

        closed_open_ratio = _closed_open_ratio(contour)
        legacy_shape_pass = closed_open_ratio is not None and (
            closed_open_ratio <= 0.9 or closed_open_ratio >= 1.06
        )
        if legacy_shape_pass:
            accepted.append(contour)
            decisions.append(
                _GreenContourFilterDecision(
                    bbox=bbox,
                    area=area,
                    closed_open_ratio=closed_open_ratio,
                    inside_max=None,
                    inside_p90=None,
                    ring_p90=None,
                    max_over_ring_p90=None,
                    p90_over_ring_p90=None,
                    ring_pixel_count=0,
                    decision_reason="accepted_shape",
                )
            )
            continue

        filled_mask = contour_to_mask(contour, gray_green.shape)
        ring_mask = cv2.dilate(filled_mask, kernel, iterations=1)
        ring_mask = cv2.subtract(ring_mask, filled_mask)
        ring_pixel_count = int(np.count_nonzero(ring_mask))
        if ring_pixel_count == 0:
            decisions.append(
                _GreenContourFilterDecision(
                    bbox=bbox,
                    area=area,
                    closed_open_ratio=closed_open_ratio,
                    inside_max=None,
                    inside_p90=None,
                    ring_p90=None,
                    max_over_ring_p90=None,
                    p90_over_ring_p90=None,
                    ring_pixel_count=0,
                    decision_reason="rejected_shape",
                )
            )
            continue

        inside_values = gray_green[filled_mask > 0]
        ring_values = gray_green[ring_mask > 0]
        inside_max = float(np.max(inside_values))
        inside_p90 = float(np.percentile(inside_values, 90))
        ring_p90 = float(np.percentile(ring_values, 90))
        ring_reference = max(ring_p90, GREEN_RING_P90_FLOOR)
        max_over_ring_p90 = inside_max / ring_reference
        p90_over_ring_p90 = inside_p90 / ring_reference

        if (
            max_over_ring_p90 >= GREEN_STRONG_PEAK_MAX_RATIO
            and p90_over_ring_p90 >= GREEN_STRONG_PEAK_P90_RATIO
        ):
            accepted.append(contour)
            decision_reason = "accepted_strong_peak"
        else:
            decision_reason = "rejected_shape"

        decisions.append(
            _GreenContourFilterDecision(
                bbox=bbox,
                area=area,
                closed_open_ratio=closed_open_ratio,
                inside_max=inside_max,
                inside_p90=inside_p90,
                ring_p90=ring_p90,
                max_over_ring_p90=max_over_ring_p90,
                p90_over_ring_p90=p90_over_ring_p90,
                ring_pixel_count=ring_pixel_count,
                decision_reason=decision_reason,
            )
        )

    _log_green_contour_filter_decisions(decisions)
    return accepted, decisions


def filterContours(contours):
    """Remove small or obviously invalid contours from the green contour set."""

    contours = [cnt for cnt in contours if cv2.contourArea(cnt) >= 8]
    ret = []
    for cnt in contours:
        closed = cv2.arcLength(cnt, True)
        opened = cv2.arcLength(cnt, False)
        if (closed / opened) <= 0.9 or (closed / opened) >= 1.06:
            ret.append(cnt)
    return ret

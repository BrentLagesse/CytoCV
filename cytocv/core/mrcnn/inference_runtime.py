from __future__ import annotations

import os
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ["KERAS_BACKEND"] = "tensorflow"
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")

from core.mrcnn import config
import core

INFERENCE_RANDOM_SEED = 123
_WEIGHTS_FILE_NAME = "deepretina_final.h5"
_SHARED_MODEL_DIR_NAME = "mrcnn-runtime"


class BowlConfig(config.Config):
    """Mask R-CNN inference configuration for yeast-cell detection."""

    NAME = "Inference"

    IMAGE_RESIZE_MODE = "pad64"
    ZOOM = False
    ASPECT_RATIO = 1
    MIN_ENLARGE = 1
    IMAGE_MIN_SCALE = False

    IMAGE_MIN_DIM = 512
    IMAGE_MAX_DIM = False

    GPU_COUNT = 1
    IMAGES_PER_GPU = 1

    DETECTION_MAX_INSTANCES = 512
    DETECTION_NMS_THRESHOLD = 0.2
    DETECTION_MIN_CONFIDENCE = 0.9

    LEARNING_RATE = 0.001

    NUM_CLASSES = 1 + 1
    RPN_ANCHOR_SCALES = (8, 16, 32, 64, 128)
    TRAIN_ROIS_PER_IMAGE = 600
    USE_MINI_MASK = True


@dataclass(frozen=True, slots=True)
class InferenceRuntimeKey:
    """Stable cache key for a loaded inference runtime."""

    weights_path: Path
    weights_mtime_ns: int
    weights_size: int


@dataclass(slots=True)
class InferenceRuntime:
    """Loaded inference dependencies and model instance for one worker."""

    tensorflow: ModuleType
    modellib: ModuleType
    model: Any
    cache_key: InferenceRuntimeKey
    detect_lock: Any = field(default_factory=threading.Lock)


_runtime_lock = threading.Lock()
_runtime: InferenceRuntime | None = None


def _resolve_weights_path() -> Path:
    """Return the resolved Mask R-CNN weights path or raise explicitly."""

    weights_path = (Path(core.__file__).resolve().parent / "weights" / _WEIGHTS_FILE_NAME).resolve()
    if not weights_path.is_file():
        raise FileNotFoundError(f"Mask R-CNN weights file not found: {weights_path}")
    return weights_path


def _resolve_runtime_cache_key() -> InferenceRuntimeKey:
    """Build a deterministic cache key from the active weights file."""

    weights_path = _resolve_weights_path()
    stat_result = weights_path.stat()
    weights_mtime_ns = getattr(stat_result, "st_mtime_ns", int(stat_result.st_mtime * 1_000_000_000))
    return InferenceRuntimeKey(
        weights_path=weights_path,
        weights_mtime_ns=int(weights_mtime_ns),
        weights_size=int(stat_result.st_size),
    )


def _shared_model_dir() -> Path:
    """Return the shared temp model directory used by inference runtimes."""

    model_dir = Path(tempfile.gettempdir()).resolve() / "cytocv" / _SHARED_MODEL_DIR_NAME
    model_dir.mkdir(parents=True, exist_ok=True)
    return model_dir


def _build_inference_runtime(cache_key: InferenceRuntimeKey) -> InferenceRuntime:
    """Load TensorFlow, construct the inference model, and load weights once."""

    import tensorflow as tf
    from ..mrcnn import model as modellib

    tf.random.set_seed(INFERENCE_RANDOM_SEED)

    model = modellib.MaskRCNN(
        mode="inference",
        config=BowlConfig(),
        model_dir=_shared_model_dir(),
    )
    model.load_weights(str(cache_key.weights_path), by_name=True)

    return InferenceRuntime(
        tensorflow=tf,
        modellib=modellib,
        model=model,
        cache_key=cache_key,
    )


def get_inference_runtime() -> InferenceRuntime:
    """Return the process-local inference runtime, rebuilding when weights change."""

    global _runtime

    with _runtime_lock:
        cache_key = _resolve_runtime_cache_key()
        if _runtime is not None and _runtime.cache_key == cache_key:
            return _runtime

        _runtime = _build_inference_runtime(cache_key)
        return _runtime


def clear_inference_runtime_cache() -> None:
    """Reset the process-local inference runtime for tests or process refresh."""

    global _runtime

    with _runtime_lock:
        _runtime = None


__all__ = [
    "BowlConfig",
    "INFERENCE_RANDOM_SEED",
    "InferenceRuntime",
    "InferenceRuntimeKey",
    "clear_inference_runtime_cache",
    "get_inference_runtime",
]

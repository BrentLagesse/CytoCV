from __future__ import annotations

import os


def configure_environment(*, cpu_only: bool = False) -> None:
    """Set TensorFlow/Keras environment flags before importing ML libraries."""

    os.environ.setdefault("KERAS_BACKEND", "tensorflow")
    os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")

    if cpu_only:
        os.environ.setdefault("CUDA_DEVICE_ORDER", "PCI_BUS_ID")
        os.environ["CUDA_VISIBLE_DEVICES"] = ""


__all__ = ["configure_environment"]

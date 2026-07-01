"""Compatibility loader for the legacy Keras Mask R-CNN weights file.

The bundled weights were produced for an older Keras HDF5 layout. This module
keeps loading explicit and local rather than depending on TensorFlow private
helpers whose signatures changed across releases.
"""

from __future__ import annotations

from collections import defaultdict

import h5py
import numpy as np


def load_legacy_hdf5_weights(model, filepath, *, by_name: bool = False, exclude=None) -> None:
    """Load legacy Keras `.h5` weights without TensorFlow private APIs."""

    excluded_names = set(exclude or [])
    target_model = model.inner_model if hasattr(model, "inner_model") else model

    if exclude:
        by_name = True

    with h5py.File(filepath, mode="r") as handle:
        weights_group = handle
        if "layer_names" not in handle.attrs and "model_weights" in handle:
            weights_group = handle["model_weights"]

        if by_name:
            _load_weights_by_name(weights_group, target_model, excluded_names)
        else:
            _load_weights_topological(weights_group, target_model, excluded_names)


def _load_weights_topological(weights_group, model, excluded_names: set[str]) -> None:
    """Assign saved layers in file order when the caller does not load by name."""

    filtered_layers = [
        layer
        for layer in model.layers
        if _legacy_layer_weights(layer) and layer.name not in excluded_names
    ]
    filtered_layer_names = [
        name
        for name in _load_attributes_from_hdf5_group(weights_group, "layer_names")
        if name in weights_group and _load_attributes_from_hdf5_group(weights_group[name], "weight_names")
    ]

    if len(filtered_layer_names) != len(filtered_layers):
        raise ValueError(
            "Layer count mismatch when loading weights from file. "
            f"File has {len(filtered_layer_names)} weighted layer(s), "
            f"model expects {len(filtered_layers)}."
        )

    for name, layer in zip(filtered_layer_names, filtered_layers):
        saved_group = weights_group[name]
        _assign_layer_weights(
            layer,
            weight_values=_load_subset_weights_from_hdf5_group(saved_group),
        )

    if "top_level_model_weights" in weights_group:
        symbolic_weights = _legacy_model_weights(model)
        weight_values = _load_subset_weights_from_hdf5_group(weights_group["top_level_model_weights"])
        if len(weight_values) != len(symbolic_weights):
            raise ValueError(
                "Weight count mismatch for top-level weights when loading weights from file. "
                f"Model expects {len(symbolic_weights)} top-level weight(s). "
                f"File has {len(weight_values)}."
            )
        _assign_symbolic_weights(symbolic_weights, weight_values)


def _load_weights_by_name(weights_group, model, excluded_names: set[str]) -> None:
    """Assign matching saved layer weights by layer name, preserving exclusions."""

    index = defaultdict(list)
    for layer in model.layers:
        index[layer.name].append(layer)

    for name in _load_attributes_from_hdf5_group(weights_group, "layer_names"):
        if name not in weights_group or name in excluded_names:
            continue
        saved_group = weights_group[name]
        weight_values = _load_subset_weights_from_hdf5_group(saved_group)
        if not weight_values:
            continue
        for layer in index.get(name, []):
            _assign_layer_weights(layer, weight_values=weight_values)


def _assign_layer_weights(layer, *, weight_values: list[np.ndarray]) -> None:
    """Assign one saved HDF5 layer payload to the matching Keras layer."""

    symbolic_weights = _legacy_layer_weights(layer)
    if len(weight_values) != len(symbolic_weights):
        raise ValueError(
            f"Weight count mismatch when loading layer '{layer.name}'. "
            f"Layer expects {len(symbolic_weights)} weight(s). "
            f"File has {len(weight_values)}."
        )
    _assign_symbolic_weights(symbolic_weights, weight_values)


def _assign_symbolic_weights(symbolic_weights, weight_values: list[np.ndarray]) -> None:
    """Write concrete arrays into Keras symbolic weight variables."""

    for reference, value in zip(symbolic_weights, weight_values):
        reference.assign(value)


def _decode_attribute_value(value):
    """Normalize HDF5 attribute values across bytes/string storage variants."""

    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


def _load_attributes_from_hdf5_group(group, name: str) -> list[str]:
    """Read legacy Keras attributes that may be stored in numbered chunks."""

    values = []
    if name in group.attrs:
        values.extend(group.attrs[name])
    else:
        index = 0
        while f"{name}{index}" in group.attrs:
            values.extend(group.attrs[f"{name}{index}"])
            index += 1
    return [_decode_attribute_value(value) for value in values]


def _legacy_model_weights(model) -> list[object]:
    """Return model-level weights in the order expected by legacy Keras files."""

    return list(model.trainable_weights) + list(model.non_trainable_weights)


def _legacy_layer_weights(layer) -> list[object]:
    """Return layer weights in the trainable then non-trainable legacy order."""

    return list(layer.trainable_weights) + list(layer.non_trainable_weights)


def _load_subset_weights_from_hdf5_group(group) -> list[np.ndarray]:
    """Load one layer/group weight array list by its saved weight-name order."""

    return [
        np.asarray(group[weight_name])
        for weight_name in _load_attributes_from_hdf5_group(group, "weight_names")
    ]


__all__ = ["load_legacy_hdf5_weights"]

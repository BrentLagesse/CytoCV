"""Core view modules.

Keep this package initializer import-light so background services can import
submodules such as ``core.views.segment_image`` without triggering unrelated
view imports and circular dependencies.
"""

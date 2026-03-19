# Glossary

## Biology And Imaging Terms

### DeltaVision (`DV`)

A microscopy file format used as the primary CytoCV input type.

### DIC

Differential Interference Contrast. In CytoCV, this is the structural brightfield-like channel used for segmentation.

### DAPI

Blue fluorescence channel used for nucleus-related reference and some legacy intensity measurements.

### mCherry

Red fluorescence channel used for spindle pole body or red-signal measurements.

### GFP

Green fluorescence channel used for GFP-related measurements and dot classification.

### Microns Per Pixel

Physical size calibration used to convert between pixel distances and real-space measurements.

## Application Terms

### Upload Queue

The set of valid runs collected during the upload step before preprocessing begins.

### Preview Asset

A browser-friendly generated PNG representing a DV layer before main processing.

### Transient Run

A completed run that is still available to the current session but not retained as a saved account file.

### Saved Run

A run retained under the authenticated account and included in dashboard history.

### Channel Configuration

The saved mapping of logical channel names to layer indices for a given run.

### Plugin

A unit of per-cell analysis logic declared in `core.stats_plugins` and executed during segmentation statistics calculation.

### Nuclear Or Cellular Mode

The current mode used by the modern nuclear/cellular intensity workflow to determine which channel supplies the contour source and which channel is measured.

## Related Documents

- [`data-model.md`](data-model.md)
- [`file-format-and-artifact-spec.md`](file-format-and-artifact-spec.md)

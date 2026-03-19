# Backup Retention And Storage

## Purpose

This document explains retained storage, transient artifacts, and the backup priorities for the current application.

## Storage Model

CytoCV stores data in two major persistence layers:

- the relational database
- the media filesystem under `MEDIA_ROOT`

The database tracks ownership and statistics metadata. The media filesystem stores uploaded DV files and generated image artifacts.

## Media Layout

For each run UUID, CytoCV can use:

- `MEDIA_ROOT/<uuid>/`
- `MEDIA_ROOT/<uuid>/preview/`
- `MEDIA_ROOT/<uuid>/pre_process/`
- `MEDIA_ROOT/<uuid>/output/`
- `MEDIA_ROOT/<uuid>/segmented/`
- `MEDIA_ROOT/user_<uuid>/`

## Retained Versus Regenerable Data

Retained data:

- uploaded source DV files
- saved run outputs
- database rows for saved runs

Regenerable or cleanup-eligible data:

- preview assets
- transient preprocess artifacts
- some inference and log artifacts

## Cleanup Behavior

CytoCV actively cleans:

- failed partial processing outputs
- transient preprocess artifacts after successful segmentation
- stale unsaved runs past the retention window

## User Storage Quota

Authenticated users have:

- `total_storage`
- `used_storage`
- `available_storage`

Quota checks are enforced before converting transient runs into retained saved runs.

## Backup Priorities

Highest backup priority:

- PostgreSQL database
- uploaded DV source files
- saved segmentation output directories

Lower backup priority:

- preview assets
- transient preprocess artifacts
- local caches

## Restore Priority

To restore user-visible functionality, prioritize:

1. database restore
2. retained uploaded DV files
3. retained output and segmented image directories
4. optional regeneration of previews or transient artifacts if needed

## Related Documents

- [`deployment-guide.md`](deployment-guide.md)
- [`security-and-privacy.md`](security-and-privacy.md)
- [`../developer/data-flow-and-artifacts.md`](../developer/data-flow-and-artifacts.md)

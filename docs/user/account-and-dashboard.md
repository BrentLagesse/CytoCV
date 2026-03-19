# Account And Dashboard

## Purpose

This guide explains how account management, saved files, and dashboard history behave.

## Prerequisites

- a running CytoCV instance
- a registered account for dashboard and settings features

## Account Flows

CytoCV supports:

- email/password signup
- email/password login
- password recovery by verification code
- optional Google OAuth
- optional Microsoft OAuth
- optional reCAPTCHA gating around auth-related flows

Account settings include:

- account identity display
- account deletion with email confirmation

## Workflow Defaults

Authenticated users can save workflow defaults for:

- selected plugins
- validation module behavior
- layer and wavelength enforcement
- manual required channels
- autosave behavior
- channel and scale visibility in sidebars
- default threshold, length, and scale settings

These settings are persisted in the user `config` JSON field.

## Dashboard Behavior

The dashboard shows saved runs owned by the current user. For each saved run, the dashboard can display:

- file name
- upload date
- detected channel badges
- scale summary
- cell count
- statistics table exports

The dashboard also reports storage information:

- saved file count
- used storage
- remaining storage
- projected additional files possible, when enough saved history exists to estimate average retained run size

## Saved Versus Transient Runs

CytoCV distinguishes between:

- `saved` runs, retained under the authenticated user account
- `transient` runs, still viewable in the current session but not yet retained in dashboard history

A run becomes transient when:

- autosave is disabled
- autosave fails because of storage quota limits
- a saved run is explicitly unsaved

## Deletion Behavior

Dashboard deletion permanently removes:

- `UploadedImage` rows for the selected UUIDs
- `SegmentedImage` rows for the selected UUIDs
- media files under both the shared and `user_<uuid>` namespaces

Account deletion removes:

- the user row
- associated uploads
- associated saved segmentation rows
- associated media files

## Expected Outputs

- account-specific storage metrics
- persistent workflow defaults
- saved-run history visible in the dashboard

## Common Errors

- file unavailable during save or unsave
  The selected UUID is not currently accessible to the signed-in user.
- quota exceeded during manual save
  The selected run set would exceed remaining retained storage.
- incorrect email entered during account deletion
  The deletion confirmation did not match the active account email.

## Related Documents

- [`workflow-guide.md`](workflow-guide.md)
- [`../ops/security-and-privacy.md`](../ops/security-and-privacy.md)
- [`../reference/data-model.md`](../reference/data-model.md)

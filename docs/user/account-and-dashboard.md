# Account And Dashboard

## Purpose

This guide explains how account management, saved files, and dashboard history behave.

## Prerequisites

- a running CytoCV instance
- a registered account for dashboard and settings features

## Account Flows

CytoCV supports:

- account-based email/password sign-in
- password recovery
- optional Google sign-in
- optional Microsoft sign-in
- optional anti-abuse checks around auth-related flows

The exact sign-in options available on a given site depend on how that deployment is configured.

Account settings include:

- account identity display
- account deletion with email confirmation

## Email Verification Methods

CytoCV can use verification codes for native email flows and confirmation links for provider-backed email verification, depending on deployment settings. Available verification methods, timing, and provider behavior depend on how the site is configured.

When a deployment asks you to complete email verification, open the newest verification link in the same browser session so the app can resume sign-in automatically. If you open the link in a different browser or session, your email may still verify, but you may need to return and sign in again.

## Workflow Defaults

Authenticated users can save workflow defaults for:

- selected plugins
- validation module behavior
- layer and wavelength enforcement
- manual required channels
- autosave behavior
- channel and scale visibility in sidebars
- default threshold, length, and scale settings

These settings are saved to the user account and reused in future sessions.

## Dashboard Behavior

The dashboard shows saved runs owned by the current user. For each saved run, the dashboard can display:

- file name
- upload date
- detected channel badges
- scale summary
- cell count
- CSV or XLSX statistics-table exports

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

When autosave falls back because retained quota is full, the run remains viewable in the active session but is not added to dashboard history until it is saved later.

## Deletion Behavior

Dashboard deletion permanently removes the selected saved runs and their stored artifacts.

Account deletion removes the account and its associated saved CytoCV data.

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
- [`output-guide.md`](output-guide.md)
- [`troubleshooting.md`](troubleshooting.md)

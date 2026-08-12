"""Canonical first-party license metadata for views and templates."""

from __future__ import annotations

from django.http import HttpRequest


LICENSE_FULL_NAME = "GNU Affero General Public License v3.0 or later"
LICENSE_SPDX_ID = "AGPL-3.0-or-later"
LICENSE_OFFICIAL_URL = "https://www.gnu.org/licenses/agpl-3.0.html"
LICENSE_SPDX_URL = "https://spdx.org/licenses/AGPL-3.0-or-later.html"
REPOSITORY_URL = "https://github.com/BrentLagesse/CytoCV"
RELEASE_VERSION = "2.0.0"
RELEASE_TAG = f"v{RELEASE_VERSION}"
SOURCE_CODE_URL = f"{REPOSITORY_URL}/tree/{RELEASE_TAG}"
LICENSE_REPOSITORY_URL = f"{REPOSITORY_URL}/blob/{RELEASE_TAG}/LICENSE"
DOCUMENTATION_URL = f"{SOURCE_CODE_URL}/docs"


def license_metadata(request: HttpRequest) -> dict[str, str]:
    """Expose the canonical project license metadata to every template."""

    return {
        "license_full_name": LICENSE_FULL_NAME,
        "license_spdx_id": LICENSE_SPDX_ID,
        "license_official_url": LICENSE_OFFICIAL_URL,
        "license_spdx_url": LICENSE_SPDX_URL,
        "license_repository_url": LICENSE_REPOSITORY_URL,
        "source_code_url": SOURCE_CODE_URL,
    }

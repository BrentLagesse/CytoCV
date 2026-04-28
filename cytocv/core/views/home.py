from __future__ import annotations

from django.template.response import TemplateResponse

CC_LICENSE_NAME = "Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License"
CC_LICENSE_IDENTIFIER = "CC BY-NC-SA 4.0"
CC_LICENSE_URL = "https://creativecommons.org/licenses/by-nc-sa/4.0/"
CC_LICENSE_LEGAL_CODE_URL = "https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode.en"

LICENSE_SUMMARY_POINTS = (
    "You may copy and redistribute the material in any medium or format.",
    "You may remix, transform, and build upon the material.",
    "You must give appropriate credit, provide a link to the license, and indicate whether changes were made.",
    "You may not use the material for commercial purposes.",
    "If you adapt the material, you must distribute your contributions under the same license.",
    "You may not apply legal terms or technological measures that restrict uses the license permits.",
)

LICENSE_SCOPE_NOTE = (
    "CytoCV's current published project statement is that it is licensed under "
    "CC BY-NC-SA 4.0. If maintainers later intend different terms for source code, "
    "documentation, or other assets, that distinction should be clarified separately."
)

LICENSE_DISCLAIMER = (
    "This page is a brief summary only. Confirm reuse, attribution, noncommercial, "
    "and share-alike requirements against the official Creative Commons license and "
    "legal code."
)


def home(request):
    return TemplateResponse(request, "home.html")


def license_page(request):
    return TemplateResponse(
        request,
        "license.html",
        {
            "cc_license_name": CC_LICENSE_NAME,
            "cc_license_identifier": CC_LICENSE_IDENTIFIER,
            "cc_license_url": CC_LICENSE_URL,
            "cc_license_legal_code_url": CC_LICENSE_LEGAL_CODE_URL,
            "license_summary_points": LICENSE_SUMMARY_POINTS,
            "license_scope_note": LICENSE_SCOPE_NOTE,
            "license_disclaimer": LICENSE_DISCLAIMER,
        },
    )
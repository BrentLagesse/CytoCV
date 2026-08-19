"""Search-engine discovery and indexing policy for CytoCV."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Callable
from urllib.parse import SplitResult, urlsplit

from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest, HttpResponse
from django.template.response import TemplateResponse
from django.urls import reverse
from django.views.decorators.http import require_safe


INDEXABLE_ROUTE_NAMES = (
    "home",
    "about",
    "about_technical",
    "about_biology",
    "collaborators",
    "license",
)

ROBOTS_DISALLOWED_PATHS = (
    "/admin/",
    "/api/",
    "/media/",
    "/signin/oauth/",
)


def _configured_public_origin_parts() -> SplitResult | None:
    """Return and validate the configured public origin, when present."""

    configured_url = getattr(settings, "PUBLIC_BASE_URL", "").strip().rstrip("/")
    if not configured_url:
        return None

    parsed = urlsplit(configured_url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.path
        or parsed.query
        or parsed.fragment
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ImproperlyConfigured(
            "CYTOCV_PUBLIC_BASE_URL must be an HTTP(S) origin without a path, "
            "query string, fragment, or credentials."
        )
    return parsed


def public_origin(request: HttpRequest | None = None) -> str:
    """Return the trusted canonical origin, with a request fallback for local use."""

    configured = _configured_public_origin_parts()
    if configured is not None:
        return f"{configured.scheme}://{configured.netloc}"
    if request is None:
        raise ImproperlyConfigured(
            "CYTOCV_PUBLIC_BASE_URL is required when no request is available."
        )
    return request.build_absolute_uri("/").rstrip("/")


def public_url(path: str, request: HttpRequest | None = None) -> str:
    """Build an absolute public URL for a root-relative path."""

    normalized_path = path if path.startswith("/") else f"/{path}"
    return f"{public_origin(request)}{normalized_path}"


def indexing_directive(request: HttpRequest) -> str:
    """Return the fail-closed indexing directive for the resolved route."""

    resolver_match = getattr(request, "resolver_match", None)
    route_name = getattr(resolver_match, "url_name", None)
    return "index,follow" if route_name in INDEXABLE_ROUTE_NAMES else "noindex,follow"


def seo_metadata(request: HttpRequest) -> dict[str, str]:
    """Expose query-free canonical and robots metadata to shared templates."""

    resolver_match = getattr(request, "resolver_match", None)
    route_name = getattr(resolver_match, "url_name", None)
    is_indexable = route_name in INDEXABLE_ROUTE_NAMES
    return {
        "seo_canonical_url": (
            public_url(reverse(route_name), request) if is_indexable else ""
        ),
        "seo_public_origin": public_origin(request),
        "seo_robots_directive": indexing_directive(request),
    }


class SearchIndexingPolicyMiddleware:
    """Apply indexing policy even to responses rendered outside CytoCV templates."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        if not response.has_header("X-Robots-Tag"):
            response["X-Robots-Tag"] = indexing_directive(request)
        return response


class PublicPageSitemap(Sitemap):
    """List only the public informational pages intended for search results."""

    def items(self) -> tuple[str, ...]:
        return INDEXABLE_ROUTE_NAMES

    def location(self, item: str) -> str:
        return reverse(item)

    def get_protocol(self, protocol: str | None = None) -> str:
        configured = _configured_public_origin_parts()
        if configured is not None:
            return configured.scheme
        return super().get_protocol(protocol)

    def get_domain(self, site=None) -> str:
        configured = _configured_public_origin_parts()
        if configured is not None:
            return configured.netloc
        return super().get_domain(site)


@require_safe
def sitemap_xml(request: HttpRequest) -> HttpResponse:
    """Render the public sitemap with one origin shared by every SEO signal."""

    origin = urlsplit(public_origin(request))
    public_pages = PublicPageSitemap().get_urls(
        site=SimpleNamespace(domain=origin.netloc),
        protocol=origin.scheme,
    )
    response = TemplateResponse(
        request,
        "sitemap.xml",
        {"urlset": public_pages},
        content_type="application/xml",
    )
    response["X-Robots-Tag"] = "noindex"
    return response


@require_safe
def robots_txt(request: HttpRequest) -> HttpResponse:
    """Publish crawl rules and advertise the canonical sitemap location."""

    lines = [
        "User-agent: *",
        "Allow: /",
        *(f"Disallow: {path}" for path in ROBOTS_DISALLOWED_PATHS),
        "",
        f"Sitemap: {public_url(reverse('sitemap'), request)}",
    ]
    return HttpResponse(
        "\n".join(lines) + "\n",
        content_type="text/plain; charset=utf-8",
    )

"""Search discovery, canonical URL, and indexing-policy contracts."""

from __future__ import annotations

import re
from urllib.parse import urlsplit
from xml.etree import ElementTree

from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.test import TestCase, override_settings
from django.urls import reverse

from core.seo import INDEXABLE_ROUTE_NAMES


PUBLIC_ORIGIN = "https://cytocv.uwb.edu"
SITEMAP_NAMESPACE = {"sitemap": "http://www.sitemaps.org/schemas/sitemap/0.9"}


@override_settings(
    ALLOWED_HOSTS=["testserver", "untrusted.invalid"],
    PUBLIC_BASE_URL=PUBLIC_ORIGIN,
    RECAPTCHA_ENABLED=False,
)
class SearchIndexingTests(TestCase):
    def setUp(self):
        Site.objects.update_or_create(
            id=1,
            defaults={"domain": "wrong.invalid", "name": "Wrong test site"},
        )
        Site.objects.clear_cache()

    def tearDown(self):
        Site.objects.clear_cache()
        super().tearDown()

    @staticmethod
    def _single_match(pattern: str, html: str) -> str:
        matches = re.findall(pattern, html, flags=re.DOTALL)
        if len(matches) != 1:
            raise AssertionError(
                f"Expected exactly one match for {pattern!r}; found {len(matches)}."
            )
        return matches[0].strip()

    def test_robots_txt_publishes_exact_crawl_policy_and_sitemap(self):
        response = self.client.get(reverse("robots_txt"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/plain; charset=utf-8")
        self.assertEqual(response["X-Robots-Tag"], "noindex,follow")
        self.assertEqual(
            response.content.decode("utf-8"),
            "User-agent: *\n"
            "Allow: /\n"
            "Disallow: /admin/\n"
            "Disallow: /api/\n"
            "Disallow: /media/\n"
            "Disallow: /signin/oauth/\n"
            "\n"
            f"Sitemap: {PUBLIC_ORIGIN}/sitemap.xml\n",
        )

    def test_google_site_verification_file_is_served_from_site_root(self):
        response = self.client.get(reverse("google_site_verification"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/html; charset=utf-8")
        self.assertEqual(response["X-Robots-Tag"], "noindex,follow")
        self.assertEqual(
            response.content.decode("utf-8"),
            "google-site-verification: google97643732cc74b099.html\n",
        )

    def test_sitemap_contains_only_canonical_public_information_pages(self):
        response = self.client.get(
            reverse("sitemap"),
            secure=False,
            HTTP_HOST="untrusted.invalid",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("application/xml"))
        self.assertEqual(response["X-Robots-Tag"], "noindex")
        root = ElementTree.fromstring(response.content)
        self.assertEqual(root.tag, f"{{{SITEMAP_NAMESPACE['sitemap']}}}urlset")
        locations = [
            element.text
            for element in root.findall("sitemap:url/sitemap:loc", SITEMAP_NAMESPACE)
        ]
        expected_locations = [
            f"{PUBLIC_ORIGIN}{reverse(route_name)}"
            for route_name in INDEXABLE_ROUTE_NAMES
        ]
        self.assertEqual(locations, expected_locations)
        self.assertNotIn("wrong.invalid", response.content.decode("utf-8"))
        self.assertNotIn("untrusted.invalid", response.content.decode("utf-8"))

        excluded_prefixes = (
            "/signin/",
            "/signup/",
            "/account-settings/",
            "/dashboard/",
            "/workflow-defaults/",
            "/experiment/",
            "/api/",
            "/media/",
            "/admin/",
        )
        for location in locations:
            path = urlsplit(location or "").path
            self.assertFalse(path.startswith(excluded_prefixes), path)

    def test_public_pages_have_unique_metadata_and_canonical_signals(self):
        titles = set()
        descriptions = set()

        for route_name in INDEXABLE_ROUTE_NAMES:
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                html = response.content.decode("utf-8")
                expected_url = f"{PUBLIC_ORIGIN}{reverse(route_name)}"

                title = self._single_match(r"<title>(.*?)</title>", html)
                description = self._single_match(
                    r'<meta name="description" content="([^"]+)">',
                    html,
                )
                robots = self._single_match(
                    r'<meta name="robots" content="([^"]+)">',
                    html,
                )
                canonical = self._single_match(
                    r'<link rel="canonical" href="([^"]+)">',
                    html,
                )
                open_graph_url = self._single_match(
                    r'<meta property="og:url" content="([^"]+)">',
                    html,
                )

                self.assertTrue(title)
                self.assertTrue(description)
                self.assertEqual(robots, "index,follow")
                self.assertEqual(response["X-Robots-Tag"], "index,follow")
                self.assertEqual(canonical, expected_url)
                self.assertEqual(open_graph_url, expected_url)
                expected_social_image = (
                    f"{PUBLIC_ORIGIN}/static/assets/UWBSTEM.png?v=4"
                )
                self.assertEqual(
                    self._single_match(
                        r'<meta property="og:image" content="([^"]+)">',
                        html,
                    ),
                    expected_social_image,
                )
                self.assertEqual(
                    self._single_match(
                        r'<meta name="twitter:image" content="([^"]+)">',
                        html,
                    ),
                    expected_social_image,
                )
                titles.add(title)
                descriptions.add(description)

        self.assertEqual(len(titles), len(INDEXABLE_ROUTE_NAMES))
        self.assertEqual(len(descriptions), len(INDEXABLE_ROUTE_NAMES))

    def test_query_parameters_do_not_enter_canonical_or_open_graph_url(self):
        response = self.client.get(
            f'{reverse("about")}?utm_source=test&next=/dashboard/',
            HTTP_HOST="untrusted.invalid",
        )
        html = response.content.decode("utf-8")
        expected_url = f'{PUBLIC_ORIGIN}{reverse("about")}'

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self._single_match(
                r'<link rel="canonical" href="([^"]+)">',
                html,
            ),
            expected_url,
        )
        self.assertEqual(
            self._single_match(
                r'<meta property="og:url" content="([^"]+)">',
                html,
            ),
            expected_url,
        )
        self.assertNotIn("utm_source", html)
        self.assertNotIn("untrusted.invalid", html)

    def test_authentication_pages_are_noindex_without_public_url_signals(self):
        for path in (
            f'{reverse("signin")}?next=/dashboard/&token=secret',
            f'{reverse("signup")}?fresh=1',
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                html = response.content.decode("utf-8")
                self.assertEqual(
                    self._single_match(
                        r'<meta name="robots" content="([^"]+)">',
                        html,
                    ),
                    "noindex,follow",
                )
                self.assertEqual(response["X-Robots-Tag"], "noindex,follow")
                self.assertNotIn('rel="canonical"', html)
                self.assertNotIn('property="og:url"', html)
                self.assertNotIn("token=secret", html)

    def test_authenticated_application_page_is_noindex(self):
        user = get_user_model().objects.create_user(
            email="seo-test@example.com",
            password="TestPass123!",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertEqual(
            self._single_match(
                r'<meta name="robots" content="([^"]+)">',
                html,
            ),
            "noindex,follow",
        )
        self.assertEqual(response["X-Robots-Tag"], "noindex,follow")
        self.assertNotIn('rel="canonical"', html)
        self.assertNotIn('property="og:url"', html)

    def test_allauth_pages_receive_noindex_response_header(self):
        response = self.client.get(reverse("account_login"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Robots-Tag"], "noindex,follow")

    @override_settings(
        ALLOWED_HOSTS=["fallback.invalid"],
        PUBLIC_BASE_URL="",
    )
    def test_request_origin_fallback_is_shared_by_every_discovery_endpoint(self):
        request_options = {"secure": True, "HTTP_HOST": "fallback.invalid"}
        expected_origin = "https://fallback.invalid"

        home_response = self.client.get(reverse("home"), **request_options)
        robots_response = self.client.get(reverse("robots_txt"), **request_options)
        sitemap_response = self.client.get(reverse("sitemap"), **request_options)

        self.assertEqual(home_response.status_code, 200)
        self.assertContains(
            home_response,
            f'<link rel="canonical" href="{expected_origin}/">',
            html=True,
        )
        self.assertIn(
            f"Sitemap: {expected_origin}/sitemap.xml",
            robots_response.content.decode("utf-8"),
        )
        root = ElementTree.fromstring(sitemap_response.content)
        locations = [
            element.text
            for element in root.findall("sitemap:url/sitemap:loc", SITEMAP_NAMESPACE)
        ]
        self.assertEqual(
            locations,
            [
                f"{expected_origin}{reverse(route_name)}"
                for route_name in INDEXABLE_ROUTE_NAMES
            ],
        )
        self.assertNotIn("wrong.invalid", sitemap_response.content.decode("utf-8"))

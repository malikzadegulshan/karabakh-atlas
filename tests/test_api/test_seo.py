#!/usr/bin/python3
"""Tests for the crawler-facing pages: per-place share page (Open Graph /
Twitter tags), sitemap.xml and robots.txt."""
import os
import unittest
import uuid
from unittest import mock
from xml.etree import ElementTree
from api.v1 import seo
from api.v1.app import app
from models import storage
from models.city import City
from models.region import Region

FRONTEND = "http://localhost:8000"


def _make_city(**overrides):
    region = Region(name="SEO Region {}".format(uuid.uuid4()))
    region.save()
    fields = {
        "name": "Shusha", "region_id": region.id,
        "latitude": 39.76, "longitude": 46.75,
    }
    fields.update(overrides)
    city = City(**fields)
    city.save()
    return city


class TestSharePage(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()

    def test_unknown_place_is_404(self):
        self.assertEqual(self.client.get("/p/nope").status_code, 404)

    def test_tags_carry_name_description_and_image(self):
        city = _make_city(
            description="A fortress town.",
            image_url="https://example.com/shusha.jpg")
        resp = self.client.get("/p/{}".format(city.id))
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn(
            '<meta property="og:title" content="Shusha — Dirchalish">', html)
        self.assertIn(
            '<meta property="og:description" content="A fortress town.">',
            html)
        self.assertIn('name="twitter:card" content="summary_large_image"',
                      html)
        self.assertIn("images.weserv.nl", html)
        self.assertIn("url=https%3A%2F%2Fexample.com%2Fshusha.jpg", html)
        self.assertIn(
            'og:url" content="http://localhost/p/{}"'.format(city.id), html)
        self.assertIn("{}/?place={}".format(FRONTEND, city.id), html)
        self.assertIn('http-equiv="refresh"', html)
        self.assertEqual(resp.headers["Content-Type"],
                         "text/html; charset=utf-8")

    def test_no_photo_falls_back_to_the_site_card(self):
        city = _make_city()
        html = self.client.get("/p/{}".format(city.id)).get_data(as_text=True)
        self.assertIn(
            'og:image" content="{}/og-image.png"'.format(FRONTEND), html)
        self.assertIn(
            'twitter:image" content="{}/og-image.png"'.format(FRONTEND), html)
        self.assertIn("Explore Shusha", html)

    def test_non_http_image_is_dropped(self):
        city = _make_city(image_url="javascript:alert(1)")
        html = self.client.get("/p/{}".format(city.id)).get_data(as_text=True)
        self.assertNotIn("javascript", html)
        self.assertIn("{}/og-image.png".format(FRONTEND), html)

    def test_user_text_is_escaped(self):
        city = _make_city(
            name='"><script>alert(1)</script>',
            description='x" onload="alert(1)')
        html = self.client.get("/p/{}".format(city.id)).get_data(as_text=True)
        self.assertNotIn("<script>", html)
        self.assertNotIn('onload="alert', html)

    def test_language_picks_translations_and_fallback(self):
        city = _make_city(
            name_i18n={"az": "Şuşa"}, description_i18n={"az": "Qala şəhəri"})
        az = self.client.get(
            "/p/{}?lang=az".format(city.id)).get_data(as_text=True)
        self.assertIn('lang="az"', az)
        self.assertIn("Şuşa — Dirchalish", az)
        self.assertIn("Qala şəhəri", az)
        self.assertIn("lang=az", az)
        # No Turkish translation -> falls back to the English name.
        tr = self.client.get(
            "/p/{}?lang=tr".format(city.id)).get_data(as_text=True)
        self.assertIn("Shusha — Dirchalish", tr)
        # Unsupported language -> English.
        xx = self.client.get(
            "/p/{}?lang=xx".format(city.id)).get_data(as_text=True)
        self.assertIn('lang="en"', xx)

    def test_long_description_is_clipped_on_a_word(self):
        text = "word " * 100
        out = seo.build_description(text, "fallback")
        self.assertLessEqual(len(out), seo.DESCRIPTION_MAX_CHARS)
        self.assertTrue(out.endswith("word…"))
        self.assertEqual(seo.build_description("  \n ", "fallback"),
                         "fallback")


class TestPublicUrlPinning(unittest.TestCase):
    """With KBA_PUBLIC_URL set, a spoofed Host header must not reach the
    canonical/og:url links, the sitemap or robots.txt."""

    PUBLIC = "https://api.example.org"

    def setUp(self):
        self.client = app.test_client()
        patcher = mock.patch.dict(os.environ, {
            "KBA_PUBLIC_URL": self.PUBLIC + "/"})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_spoofed_host_is_ignored(self):
        city = _make_city()
        evil = {"Host": "evil.example",
                "X-Forwarded-Host": "evil.example"}
        html = self.client.get(
            "/p/{}".format(city.id), headers=evil).get_data(as_text=True)
        self.assertNotIn("evil.example", html)
        self.assertIn(
            'og:url" content="{}/p/{}"'.format(self.PUBLIC, city.id), html)
        self.assertIn('rel="canonical" href="{}/p/{}"'.format(
            self.PUBLIC, city.id), html)
        robots = self.client.get(
            "/robots.txt", headers=evil).get_data(as_text=True)
        self.assertIn("Sitemap: {}/sitemap.xml".format(self.PUBLIC), robots)
        self.assertNotIn("evil.example", robots)
        sitemap = self.client.get(
            "/sitemap.xml", headers=evil).get_data(as_text=True)
        self.assertNotIn("evil.example", sitemap)
        self.assertIn("{}/p/{}".format(self.PUBLIC, city.id), sitemap)


class TestSitemapAndRobots(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()

    def test_sitemap_lists_places(self):
        city = _make_city(name="Sitemap & Co")
        resp = self.client.get("/sitemap.xml")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.mimetype, "application/xml")
        root = ElementTree.fromstring(resp.data)
        ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        locs = [e.text for e in root.findall("s:url/s:loc", ns)]
        self.assertIn("http://localhost/p/{}".format(city.id), locs)

    def test_robots_points_at_sitemap_and_hides_api(self):
        body = self.client.get("/robots.txt").get_data(as_text=True)
        self.assertIn("Disallow: /api/", body)
        self.assertIn("Sitemap: http://localhost/sitemap.xml", body)

    def test_share_page_not_affected_by_storage_cleanup(self):
        # Sanity: the page reads live data, so a deleted place 404s.
        city = _make_city()
        city_id = city.id
        city.delete()
        storage.save()
        self.assertEqual(self.client.get("/p/" + city_id).status_code, 404)


if __name__ == "__main__":
    unittest.main()

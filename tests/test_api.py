#!/usr/bin/python3
"""Integration tests for core API views: regions, cities, bulk import,
historical events, news, favorites, images, SEO, and contribution tiers."""
from datetime import datetime
import io
import json
import os
import unittest
from unittest import mock
import uuid
from xml.etree import ElementTree
from api.v1.app import app
from api.v1 import auth_utils
from api.v1.contributions import approved_post_count, contribution_tier
from api.v1 import seo
from models import storage
from models.city import City
from models.forum_post import ForumPost
from models.region import Region
from models.user import User

TEST_PASSWORD = "correcthorsebattery"
PASSWORD = TEST_PASSWORD
CURRENT_YEAR = datetime.utcnow().year
FRONTEND = "http://localhost:8000"

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG_BYTES = b"\xff\xd8\xff" + b"\x00" * 32
GIF_BYTES = b"GIF89a" + b"\x00" * 32
WEBP_BYTES = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 32


def register_and_login(client, name, email, password):
    """Give `client` a signed-in, approved regular user."""
    user = User(
        name=name, email=email, role="user", approved=True,
        email_verified=False)
    user.set_password(password)
    user.save()
    return client.post(
        "/api/v1/auth/login",
        data=json.dumps({"email": email, "password": password}),
        content_type="application/json")


def _unique_email():
    return "user-{}@example.com".format(uuid.uuid4())


def _email():
    return _unique_email()


def _post(client, url, payload):
    return client.post(
        url, data=json.dumps(payload), content_type="application/json")


def _json(client, method, url, payload=None):
    return getattr(client, method)(
        url,
        data=json.dumps(payload) if payload is not None else None,
        content_type="application/json")


def _path(absolute_url):
    """Strip an image URL's host, since the test client takes paths."""
    return "/api/v1" + absolute_url.split("/api/v1")[1]


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


def _make_post(author_id, status="approved", body="Test post"):
    post = ForumPost(author_id=author_id, body=body, status=status)
    post.save()
    return post


class TestAPIViews(unittest.TestCase):
    """End-to-end tests against the Flask test client."""

    def setUp(self):
        self.client = app.test_client()
        admin = User(
            name="Test Admin",
            email="test-admin-{}@example.com".format(uuid.uuid4()),
            role="admin")
        admin.set_password(TEST_PASSWORD)
        admin.save()
        login_resp = self.client.post(
            "/api/v1/auth/login",
            data=json.dumps(
                {"email": admin.email, "password": TEST_PASSWORD}),
            content_type="application/json")
        self.assertEqual(login_resp.status_code, 200)

    def test_status(self):
        """GET /api/v1/status returns OK."""
        response = self.client.get("/api/v1/status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.data), {"status": "OK"})

    def _create_region(self):
        return json.loads(self.client.post(
            "/api/v1/regions",
            data=json.dumps({"name": "Region-{}".format(uuid.uuid4())}),
            content_type="application/json").data)

    def _create_city(self, region_id, category="city"):
        return json.loads(self.client.post(
            "/api/v1/regions/{}/cities".format(region_id),
            data=json.dumps({
                "name": "Place-{}".format(uuid.uuid4()),
                "latitude": 39.8, "longitude": 46.75,
                "category": category,
            }),
            content_type="application/json").data)

    def test_stats_counts_regions_cities_and_pois_separately(self):
        region = self._create_region()
        self._create_city(region["id"], category="city")
        self._create_city(region["id"], category="museum")
        self._create_city(region["id"], category="museum")
        self._create_city(region["id"], category="cafe")

        stats = json.loads(self.client.get("/api/v1/stats").data)
        self.assertGreaterEqual(stats["regions"], 1)
        self.assertGreaterEqual(stats["cities"], 1)
        self.assertGreaterEqual(stats["points_of_interest"], 3)
        self.assertGreaterEqual(stats["categories"].get("museum", 0), 2)
        self.assertGreaterEqual(stats["categories"].get("cafe", 0), 1)
        self.assertNotIn("city", stats["categories"])

    def test_stats_forum_posts_counts_approved_only(self):
        region = self._create_region()
        city = self._create_city(region["id"])
        before = json.loads(self.client.get("/api/v1/stats").data)

        self.client.post(
            "/api/v1/forum/posts",
            data=json.dumps(
                {"body": "Nice place", "target_city_id": city["id"]}),
            content_type="application/json")

        after = json.loads(self.client.get("/api/v1/stats").data)
        self.assertEqual(after["forum_posts"], before["forum_posts"] + 1)

    def test_stats_excludes_pending_forum_posts(self):
        regular = app.test_client()
        register_and_login(
            regular, "Regular User",
            "regular-{}@example.com".format(uuid.uuid4()), TEST_PASSWORD)
        before = json.loads(self.client.get("/api/v1/stats").data)

        regular.post(
            "/api/v1/forum/posts",
            data=json.dumps({"body": "Awaiting review"}),
            content_type="application/json")

        after = json.loads(self.client.get("/api/v1/stats").data)
        self.assertEqual(after["forum_posts"], before["forum_posts"])

    def test_stats_does_not_require_login(self):
        anon = app.test_client()
        response = anon.get("/api/v1/stats")
        self.assertEqual(response.status_code, 200)

    def test_update_city_rejects_null_category(self):
        region = self._create_region()
        city = self._create_city(region["id"], category="museum")
        resp = self.client.put(
            "/api/v1/cities/{}".format(city["id"]),
            data=json.dumps({"category": None}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 400)

        unchanged = json.loads(
            self.client.get("/api/v1/cities/{}".format(city["id"])).data)
        self.assertEqual(unchanged["category"], "museum")

    def test_create_region_requires_name(self):
        response = self.client.post(
            "/api/v1/regions",
            data=json.dumps({}),
            content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_create_region_rejects_blank_name(self):
        response = self.client.post(
            "/api/v1/regions",
            data=json.dumps({"name": "   "}),
            content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_create_city_rejects_out_of_range_latitude(self):
        region = json.loads(self.client.post(
            "/api/v1/regions",
            data=json.dumps({"name": "Region"}),
            content_type="application/json").data)
        response = self.client.post(
            "/api/v1/regions/{}/cities".format(region["id"]),
            data=json.dumps(
                {"name": "Nowhere", "latitude": 999, "longitude": 46}),
            content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_create_city_rejects_non_numeric_coordinates(self):
        region = json.loads(self.client.post(
            "/api/v1/regions",
            data=json.dumps({"name": "Region"}),
            content_type="application/json").data)
        response = self.client.post(
            "/api/v1/regions/{}/cities".format(region["id"]),
            data=json.dumps(
                {"name": "Nowhere", "latitude": "banana", "longitude": 46}),
            content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_create_city_defaults_category_to_city(self):
        region = json.loads(self.client.post(
            "/api/v1/regions",
            data=json.dumps({"name": "Region"}),
            content_type="application/json").data)
        response = self.client.post(
            "/api/v1/regions/{}/cities".format(region["id"]),
            data=json.dumps(
                {"name": "Plain City", "latitude": 1, "longitude": 1}),
            content_type="application/json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(json.loads(response.data)["category"], "city")

    def test_create_city_accepts_poi_category(self):
        region = json.loads(self.client.post(
            "/api/v1/regions",
            data=json.dumps({"name": "Region"}),
            content_type="application/json").data)
        response = self.client.post(
            "/api/v1/regions/{}/cities".format(region["id"]),
            data=json.dumps({
                "name": "Corner Cafe", "latitude": 1, "longitude": 1,
                "category": "cafe",
            }),
            content_type="application/json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(json.loads(response.data)["category"], "cafe")

    def test_create_city_accepts_phone_and_website(self):
        region = json.loads(self.client.post(
            "/api/v1/regions",
            data=json.dumps({"name": "Region"}),
            content_type="application/json").data)
        response = self.client.post(
            "/api/v1/regions/{}/cities".format(region["id"]),
            data=json.dumps({
                "name": "Corner Cafe", "latitude": 1, "longitude": 1,
                "phone": "+994 12 345 6789",
                "website": "https://example.com",
            }),
            content_type="application/json")
        self.assertEqual(response.status_code, 201)
        body = json.loads(response.data)
        self.assertEqual(body["phone"], "+994 12 345 6789")
        self.assertEqual(body["website"], "https://example.com")

    def test_create_city_rejects_oversized_phone(self):
        region = json.loads(self.client.post(
            "/api/v1/regions",
            data=json.dumps({"name": "Region"}),
            content_type="application/json").data)
        response = self.client.post(
            "/api/v1/regions/{}/cities".format(region["id"]),
            data=json.dumps({
                "name": "Corner Cafe", "latitude": 1, "longitude": 1,
                "phone": "1" * 31,
            }),
            content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_create_city_rejects_javascript_scheme_website(self):
        region = json.loads(self.client.post(
            "/api/v1/regions",
            data=json.dumps({"name": "Region"}),
            content_type="application/json").data)
        response = self.client.post(
            "/api/v1/regions/{}/cities".format(region["id"]),
            data=json.dumps({
                "name": "Corner Cafe", "latitude": 1, "longitude": 1,
                "website": "javascript:alert(document.cookie)",
            }),
            content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_create_city_rejects_javascript_scheme_image_url(self):
        region = json.loads(self.client.post(
            "/api/v1/regions",
            data=json.dumps({"name": "Region"}),
            content_type="application/json").data)
        response = self.client.post(
            "/api/v1/regions/{}/cities".format(region["id"]),
            data=json.dumps({
                "name": "Corner Cafe", "latitude": 1, "longitude": 1,
                "image_url": "javascript:alert(1)",
            }),
            content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_create_city_accepts_before_photo(self):
        region = json.loads(self.client.post(
            "/api/v1/regions",
            data=json.dumps({"name": "Region"}),
            content_type="application/json").data)
        response = self.client.post(
            "/api/v1/regions/{}/cities".format(region["id"]),
            data=json.dumps({
                "name": "Corner Cafe", "latitude": 1, "longitude": 1,
                "image_url_before": "https://example.com/before.jpg",
                "image_before_credit": "Archive photo, 1994",
            }),
            content_type="application/json")
        self.assertEqual(response.status_code, 201)
        body = json.loads(response.data)
        self.assertEqual(
            body["image_url_before"], "https://example.com/before.jpg")
        self.assertEqual(body["image_before_credit"], "Archive photo, 1994")

    def test_create_city_rejects_javascript_scheme_image_url_before(self):
        region = json.loads(self.client.post(
            "/api/v1/regions",
            data=json.dumps({"name": "Region"}),
            content_type="application/json").data)
        response = self.client.post(
            "/api/v1/regions/{}/cities".format(region["id"]),
            data=json.dumps({
                "name": "Corner Cafe", "latitude": 1, "longitude": 1,
                "image_url_before": "javascript:alert(1)",
            }),
            content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_create_city_accepts_road_category(self):
        region = json.loads(self.client.post(
            "/api/v1/regions",
            data=json.dumps({"name": "Region"}),
            content_type="application/json").data)
        response = self.client.post(
            "/api/v1/regions/{}/cities".format(region["id"]),
            data=json.dumps({
                "name": "Main Street", "latitude": 1, "longitude": 1,
                "category": "road",
            }),
            content_type="application/json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(json.loads(response.data)["category"], "road")

    def test_create_city_rejects_unknown_category(self):
        region = json.loads(self.client.post(
            "/api/v1/regions",
            data=json.dumps({"name": "Region"}),
            content_type="application/json").data)
        response = self.client.post(
            "/api/v1/regions/{}/cities".format(region["id"]),
            data=json.dumps({
                "name": "Nowhere", "latitude": 1, "longitude": 1,
                "category": "spaceport",
            }),
            content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_delete_region_cascades_to_its_cities(self):
        region = json.loads(self.client.post(
            "/api/v1/regions",
            data=json.dumps({"name": "Doomed Region"}),
            content_type="application/json").data)
        city = json.loads(self.client.post(
            "/api/v1/regions/{}/cities".format(region["id"]),
            data=json.dumps(
                {"name": "Doomed City", "latitude": 1, "longitude": 1}),
            content_type="application/json").data)

        delete_resp = self.client.delete(
            "/api/v1/regions/{}".format(region["id"]))
        self.assertEqual(delete_resp.status_code, 200)

        self.assertEqual(
            self.client.get(
                "/api/v1/cities/{}".format(city["id"])).status_code,
            404)

    def test_region_city_lifecycle(self):
        region_resp = self.client.post(
            "/api/v1/regions",
            data=json.dumps({"name": "API Test Region"}),
            content_type="application/json")
        self.assertEqual(region_resp.status_code, 201)
        region = json.loads(region_resp.data)

        city_resp = self.client.post(
            "/api/v1/regions/{}/cities".format(region["id"]),
            data=json.dumps({
                "name": "API Test City",
                "latitude": 40.0,
                "longitude": 46.0,
            }),
            content_type="application/json")
        self.assertEqual(city_resp.status_code, 201)
        city = json.loads(city_resp.data)
        self.assertEqual(city["region_id"], region["id"])

        list_resp = self.client.get(
            "/api/v1/regions/{}/cities".format(region["id"]))
        self.assertEqual(list_resp.status_code, 200)
        cities = json.loads(list_resp.data)
        self.assertTrue(any(c["id"] == city["id"] for c in cities))

    def test_get_unknown_city_404(self):
        response = self.client.get("/api/v1/cities/does-not-exist")
        self.assertEqual(response.status_code, 404)

    def test_create_region_rejects_client_supplied_id(self):
        original_resp = self.client.post(
            "/api/v1/regions",
            data=json.dumps({"name": "Original"}),
            content_type="application/json")
        original = json.loads(original_resp.data)

        attack_resp = self.client.post(
            "/api/v1/regions",
            data=json.dumps({"name": "Hijacked", "id": original["id"]}),
            content_type="application/json")
        self.assertEqual(attack_resp.status_code, 400)

        still_original = self.client.get(
            "/api/v1/regions/{}".format(original["id"]))
        self.assertEqual(
            json.loads(still_original.data)["name"], "Original")

    def test_create_city_rejects_client_supplied_id(self):
        region = json.loads(self.client.post(
            "/api/v1/regions",
            data=json.dumps({"name": "Region"}),
            content_type="application/json").data)

        original = json.loads(self.client.post(
            "/api/v1/regions/{}/cities".format(region["id"]),
            data=json.dumps(
                {"name": "Original City", "latitude": 1, "longitude": 1}),
            content_type="application/json").data)

        attack_resp = self.client.post(
            "/api/v1/regions/{}/cities".format(region["id"]),
            data=json.dumps({
                "name": "Hijacked City", "latitude": 2, "longitude": 2,
                "id": original["id"],
            }),
            content_type="application/json")
        self.assertEqual(attack_resp.status_code, 400)

        still_original = self.client.get(
            "/api/v1/cities/{}".format(original["id"]))
        self.assertEqual(
            json.loads(still_original.data)["name"], "Original City")

    def test_write_requires_login(self):
        anon_client = app.test_client()
        no_login_resp = anon_client.post(
            "/api/v1/regions",
            data=json.dumps({"name": "Should Fail"}),
            content_type="application/json")
        self.assertEqual(no_login_resp.status_code, 401)

        get_resp = anon_client.get("/api/v1/regions")
        self.assertEqual(get_resp.status_code, 200)

    def test_write_requires_admin_role_not_just_login(self):
        plain_client = app.test_client()
        user = User(
            name="Plain User",
            email="plain-user-{}@example.com".format(uuid.uuid4()),
            role="user")
        user.set_password(TEST_PASSWORD)
        user.save()
        login_resp = plain_client.post(
            "/api/v1/auth/login",
            data=json.dumps(
                {"email": user.email, "password": TEST_PASSWORD}),
            content_type="application/json")
        self.assertEqual(login_resp.status_code, 200)

        resp = plain_client.post(
            "/api/v1/regions",
            data=json.dumps({"name": "Should Fail"}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 403)


class TestImport(unittest.TestCase):
    """Preview, import, duplicates, validation, and access control."""

    def setUp(self):
        self.admin = app.test_client()
        admin = User(name="Import Admin", email=_email(), role="admin")
        admin.set_password(PASSWORD)
        admin.save()
        _post(self.admin, "/api/v1/auth/login",
              {"email": admin.email, "password": PASSWORD})
        region = json.loads(_post(self.admin, "/api/v1/regions", {
            "name": "Region-{}".format(uuid.uuid4())}).data)
        self.region_id = region["id"]
        self.url = "/api/v1/regions/{}/cities/import".format(self.region_id)

    def _import(self, rows, dry_run=False, client=None):
        return _post(client or self.admin, self.url,
                     {"rows": rows, "dry_run": dry_run})

    def _cities(self):
        return [c for c in storage.all(City).values()
                if c.region_id == self.region_id]

    def _statuses(self, resp):
        return [r["status"] for r in json.loads(resp.data)["results"]]

    def test_dry_run_reports_but_saves_nothing(self):
        resp = self._import([
            {"name": "Aghdam", "latitude": 39.99, "longitude": 46.93},
            {"name": "Fuzuli", "latitude": 39.6, "longitude": 47.14},
        ], dry_run=True)
        self.assertEqual(resp.status_code, 200)
        body = json.loads(resp.data)
        self.assertEqual(body["created"], 0)
        self.assertEqual(self._statuses(resp), ["new", "new"])
        self.assertEqual(self._cities(), [])

    def test_dry_run_is_the_default(self):
        resp = _post(self.admin, self.url, {"rows": [
            {"name": "Aghdam", "latitude": 39.99, "longitude": 46.93}]})
        self.assertEqual(json.loads(resp.data)["dry_run"], True)
        self.assertEqual(self._cities(), [])

    def test_import_creates_valid_new_places_with_all_fields(self):
        resp = self._import([{
            "name": "Fuzuli Hospital", "latitude": 39.6, "longitude": 47.14,
            "category": "hospital", "description": "Main hospital.",
            "phone": "+994 12 000 00 00", "website": "https://example.com",
            "image_url": "https://example.com/a.jpg",
            "image_credit": "Photo: someone",
            "name_i18n": {"az": "Füzuli Xəstəxanası"},
            "description_i18n": {"az": "Əsas xəstəxana."},
        }])
        self.assertEqual(json.loads(resp.data)["created"], 1)
        place = self._cities()[0]
        self.assertEqual(place.category, "hospital")
        self.assertEqual(place.region_id, self.region_id)
        self.assertEqual(place.name_i18n["az"], "Füzuli Xəstəxanası")
        self.assertEqual(place.website, "https://example.com")

    def test_category_defaults_to_city(self):
        self._import([{"name": "Aghdam", "latitude": 39.99,
                       "longitude": 46.93}])
        self.assertEqual(self._cities()[0].category, "city")

    def test_bad_rows_are_reported_and_do_not_block_good_ones(self):
        resp = self._import([
            {"name": "Good", "latitude": 39.9, "longitude": 46.9},
            {"name": "Bad lat", "latitude": 999, "longitude": 46.9},
            {"name": "", "latitude": 39.9, "longitude": 46.9},
            {"name": "Bad category", "latitude": 39.9, "longitude": 46.9,
              "category": "spaceship"},
            {"name": "Bad url", "latitude": 39.9, "longitude": 46.9,
              "website": "javascript:alert(1)"},
            {"name": "Unknown field", "latitude": 39.9, "longitude": 46.9,
              "id": "x"},
            "not an object",
        ])
        body = json.loads(resp.data)
        self.assertEqual(
            [r["status"] for r in body["results"]],
            ["new", "error", "error", "error", "error", "error", "error"])
        self.assertTrue(all(
            r["error"] for r in body["results"] if r["status"] == "error"))
        self.assertEqual(body["created"], 1)
        self.assertEqual([c.name for c in self._cities()], ["Good"])

    def test_same_name_is_skipped_ignoring_case_and_spacing(self):
        self._import([{"name": "Aghdam", "latitude": 39.99,
                       "longitude": 46.93}])
        resp = self._import([{"name": "  AGHDAM ", "latitude": 10,
                              "longitude": 10}])
        self.assertEqual(self._statuses(resp), ["duplicate"])
        self.assertEqual(
            json.loads(resp.data)["results"][0]["duplicate_of"], "Aghdam")
        self.assertEqual(len(self._cities()), 1)

    def test_a_translated_name_counts_as_the_same_place(self):
        self._import([{
            "name": "Khankendi", "latitude": 39.83, "longitude": 46.77,
            "name_i18n": {"az": "Xankəndi"}}])
        resp = self._import([{"name": "Xankəndi", "latitude": 39.83,
                              "longitude": 46.77}])
        self.assertEqual(self._statuses(resp), ["duplicate"])

    def test_cities_match_by_name_anywhere(self):
        self._import([{"name": "Shusha", "latitude": 39.76,
                       "longitude": 46.75}])
        resp = self._import([{"name": "Shusha", "latitude": 41.0,
                              "longitude": 48.0}])
        self.assertEqual(self._statuses(resp), ["duplicate"])

    def test_same_named_points_of_interest_are_different_places_when_far(
            self):
        pharmacy = {"name": "Pharmacy", "category": "pharmacy"}
        self._import([dict(pharmacy, latitude=39.76, longitude=46.75)])
        far = self._import([dict(pharmacy, latitude=39.99, longitude=46.93)])
        near = self._import([dict(pharmacy, latitude=39.7601,
                                  longitude=46.7501)])
        self.assertEqual(self._statuses(far), ["new"])
        self.assertEqual(self._statuses(near), ["duplicate"])
        self.assertEqual(len(self._cities()), 2)

    def test_duplicates_inside_the_same_file_are_skipped(self):
        resp = self._import([
            {"name": "Lachin", "latitude": 39.64, "longitude": 46.55},
            {"name": "lachin", "latitude": 39.64, "longitude": 46.55},
        ])
        self.assertEqual(self._statuses(resp), ["new", "duplicate"])
        self.assertEqual(len(self._cities()), 1)

    def test_reimporting_a_corrected_file_is_safe(self):
        rows = [
            {"name": "Aghdam", "latitude": 39.99, "longitude": 46.93},
            {"name": "Broken", "latitude": 999, "longitude": 46.93},
        ]
        self._import(rows)
        rows[1]["latitude"] = 40.1
        resp = self._import(rows)
        self.assertEqual(self._statuses(resp), ["duplicate", "new"])
        self.assertEqual(len(self._cities()), 2)

    def test_other_regions_are_not_consulted(self):
        other = json.loads(_post(self.admin, "/api/v1/regions", {
            "name": "Other-{}".format(uuid.uuid4())}).data)
        _post(self.admin, "/api/v1/regions/{}/cities".format(other["id"]),
              {"name": "Aghdam", "latitude": 39.99, "longitude": 46.93})
        resp = self._import([{"name": "Aghdam", "latitude": 39.99,
                              "longitude": 46.93}])
        self.assertEqual(self._statuses(resp), ["new"])

    def test_body_shape_is_checked(self):
        for payload in ({}, {"rows": []}, {"rows": "x"},
                        {"rows": [{"name": "A"}], "dry_run": "yes"}):
            self.assertEqual(
                _post(self.admin, self.url, payload).status_code, 400)
        self.assertEqual(
            _post(self.admin, self.url, ["x"]).status_code, 400)

    def test_row_limit(self):
        rows = [{"name": "P{}".format(i), "latitude": 39.0,
                 "longitude": 46.0} for i in range(301)]
        self.assertEqual(self._import(rows).status_code, 400)
        self.assertEqual(self._import(rows[:300], dry_run=True).status_code,
                         200)

    def test_unknown_region_is_404(self):
        resp = _post(self.admin, "/api/v1/regions/nope/cities/import",
                     {"rows": [{"name": "A", "latitude": 1, "longitude": 1}]})
        self.assertEqual(resp.status_code, 404)

    def test_only_admins_can_import(self):
        rows = [{"name": "A", "latitude": 1, "longitude": 1}]
        anon = app.test_client()
        self.assertEqual(self._import(rows, client=anon).status_code, 401)
        user = app.test_client()
        register_and_login(user, "Reader", _email(), PASSWORD)
        self.assertEqual(self._import(rows, client=user).status_code, 403)
        self.assertEqual(self._cities(), [])


class TestHistoricalEventViews(unittest.TestCase):
    """End-to-end tests for /historical-events views."""

    def setUp(self):
        self.client = app.test_client()
        admin = User(
            name="Test Admin",
            email="test-admin-{}@example.com".format(uuid.uuid4()),
            role="admin")
        admin.set_password(TEST_PASSWORD)
        admin.save()
        login_resp = self.client.post(
            "/api/v1/auth/login",
            data=json.dumps(
                {"email": admin.email, "password": TEST_PASSWORD}),
            content_type="application/json")
        self.assertEqual(login_resp.status_code, 200)

    def _create_event(self, **overrides):
        payload = {
            "title": "Sample Event",
            "year": 2020,
            "latitude": 39.8,
            "longitude": 46.75,
        }
        payload.update(overrides)
        return self.client.post(
            "/api/v1/historical-events",
            data=json.dumps(payload),
            content_type="application/json")

    def test_create_requires_admin(self):
        anon = app.test_client()
        resp = anon.post(
            "/api/v1/historical-events",
            data=json.dumps({
                "title": "X", "year": 2020, "latitude": 1, "longitude": 1,
            }),
            content_type="application/json")
        self.assertEqual(resp.status_code, 401)

    def test_create_rejects_non_admin(self):
        user_client = app.test_client()
        register_and_login(
            user_client, "Regular User",
            "user-{}@example.com".format(uuid.uuid4()), TEST_PASSWORD)
        resp = user_client.post(
            "/api/v1/historical-events",
            data=json.dumps({
                "title": "X", "year": 2020, "latitude": 1, "longitude": 1,
            }),
            content_type="application/json")
        self.assertEqual(resp.status_code, 403)

    def test_create_succeeds_for_admin(self):
        resp = self._create_event()
        self.assertEqual(resp.status_code, 201)
        body = json.loads(resp.data)
        self.assertEqual(body["title"], "Sample Event")
        self.assertEqual(body["year"], 2020)

    def test_create_rejects_year_before_imagery_floor(self):
        resp = self._create_event(year=1994)
        self.assertEqual(resp.status_code, 400)

    def test_create_rejects_year_in_the_future(self):
        resp = self._create_event(year=CURRENT_YEAR + 5)
        self.assertEqual(resp.status_code, 400)

    def test_create_rejects_non_integer_year(self):
        resp = self._create_event(year=2020.5)
        self.assertEqual(resp.status_code, 400)

    def test_create_rejects_blank_title(self):
        resp = self._create_event(title="   ")
        self.assertEqual(resp.status_code, 400)

    def test_create_rejects_out_of_range_latitude(self):
        resp = self._create_event(latitude=999)
        self.assertEqual(resp.status_code, 400)

    def test_create_rejects_javascript_scheme_source_url(self):
        resp = self._create_event(source_url="javascript:alert(1)")
        self.assertEqual(resp.status_code, 400)

    def test_create_accepts_title_and_description_i18n(self):
        resp = self._create_event(
            title_i18n={"az": "Nümunə", "tr": "Örnek", "ru": "Пример"},
            description_i18n={"az": "Təsvir"})
        self.assertEqual(resp.status_code, 201)
        body = json.loads(resp.data)
        self.assertEqual(body["title_i18n"]["tr"], "Örnek")
        self.assertEqual(body["description_i18n"]["az"], "Təsvir")

    def test_create_rejects_non_string_i18n_values(self):
        resp = self._create_event(title_i18n={"az": 5})
        self.assertEqual(resp.status_code, 400)

    def test_list_is_publicly_readable(self):
        self._create_event(title="Public Event")
        anon = app.test_client()
        resp = anon.get("/api/v1/historical-events")
        self.assertEqual(resp.status_code, 200)
        titles = [e["title"] for e in json.loads(resp.data)]
        self.assertIn("Public Event", titles)

    def test_list_sorted_by_year(self):
        self._create_event(title="Later", year=2022)
        self._create_event(title="Earlier", year=2016)
        resp = self.client.get("/api/v1/historical-events")
        titles = [e["title"] for e in json.loads(resp.data)]
        self.assertLess(titles.index("Earlier"), titles.index("Later"))

    def test_update_requires_admin(self):
        create_resp = self._create_event()
        event_id = json.loads(create_resp.data)["id"]
        anon = app.test_client()
        resp = anon.put(
            "/api/v1/historical-events/{}".format(event_id),
            data=json.dumps({"title": "Renamed"}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 401)

    def test_update_succeeds_for_admin(self):
        create_resp = self._create_event()
        event_id = json.loads(create_resp.data)["id"]
        resp = self.client.put(
            "/api/v1/historical-events/{}".format(event_id),
            data=json.dumps({"title": "Renamed"}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(json.loads(resp.data)["title"], "Renamed")

    def test_update_missing_event_returns_404(self):
        resp = self.client.put(
            "/api/v1/historical-events/does-not-exist",
            data=json.dumps({"title": "Renamed"}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 404)

    def test_delete_requires_admin(self):
        create_resp = self._create_event()
        event_id = json.loads(create_resp.data)["id"]
        anon = app.test_client()
        resp = anon.delete("/api/v1/historical-events/{}".format(event_id))
        self.assertEqual(resp.status_code, 401)

    def test_delete_succeeds_for_admin(self):
        create_resp = self._create_event()
        event_id = json.loads(create_resp.data)["id"]
        resp = self.client.delete(
            "/api/v1/historical-events/{}".format(event_id))
        self.assertEqual(resp.status_code, 200)
        get_resp = self.client.get("/api/v1/historical-events")
        ids = [e["id"] for e in json.loads(get_resp.data)]
        self.assertNotIn(event_id, ids)


class TestNewsViews(unittest.TestCase):
    """End-to-end tests for /news views and news comments."""

    def setUp(self):
        auth_utils.forum_post_limiter._attempts.clear()
        auth_utils.login_limiter._attempts.clear()
        auth_utils.register_limiter._attempts.clear()

        self.admin_client = app.test_client()
        admin = User(
            name="News Admin", email=_unique_email(), role="admin")
        admin.set_password(TEST_PASSWORD)
        admin.save()
        _json(self.admin_client, "post", "/api/v1/auth/login",
              {"email": admin.email, "password": TEST_PASSWORD})

        self.client = app.test_client()
        resp = register_and_login(
            self.client, "Reader", _unique_email(), TEST_PASSWORD)
        self.reader_id = json.loads(resp.data)["id"]

    def _create_news(self, **overrides):
        payload = {"title": "Headline", "body": "Story text."}
        payload.update(overrides)
        return _json(self.admin_client, "post", "/api/v1/news", payload)

    def test_create_requires_login(self):
        resp = _json(app.test_client(), "post", "/api/v1/news",
                     {"title": "X", "body": "Y"})
        self.assertEqual(resp.status_code, 401)

    def test_create_rejects_non_admin(self):
        resp = _json(self.client, "post", "/api/v1/news",
                     {"title": "X", "body": "Y"})
        self.assertEqual(resp.status_code, 403)

    def test_update_and_delete_reject_non_admin(self):
        news_id = json.loads(self._create_news().data)["id"]
        put = _json(self.client, "put", "/api/v1/news/" + news_id,
                    {"title": "Hijacked"})
        self.assertEqual(put.status_code, 403)
        delete = self.client.delete("/api/v1/news/" + news_id)
        self.assertEqual(delete.status_code, 403)

    def test_create_succeeds_for_admin(self):
        resp = self._create_news(image_url="https://example.com/p.jpg")
        self.assertEqual(resp.status_code, 201)
        body = json.loads(resp.data)
        self.assertEqual(body["title"], "Headline")
        self.assertEqual(body["image_url"], "https://example.com/p.jpg")
        self.assertEqual(body["comment_count"], 0)

    def test_create_rejects_blank_title_and_body(self):
        self.assertEqual(self._create_news(title="  ").status_code, 400)
        self.assertEqual(self._create_news(body="").status_code, 400)

    def test_create_rejects_javascript_image_url(self):
        self.assertEqual(
            self._create_news(image_url="javascript:alert(1)").status_code,
            400)
        self.assertEqual(
            self._create_news(source_url="javascript:alert(1)").status_code,
            400)

    def test_create_rejects_unknown_fields(self):
        self.assertEqual(self._create_news(id="x").status_code, 400)

    def test_update_changes_fields(self):
        news_id = json.loads(self._create_news().data)["id"]
        resp = _json(self.admin_client, "put", "/api/v1/news/" + news_id,
                     {"title": "Edited"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(json.loads(resp.data)["title"], "Edited")

    def test_update_missing_returns_404(self):
        resp = _json(self.admin_client, "put", "/api/v1/news/nope",
                     {"title": "X"})
        self.assertEqual(resp.status_code, 404)

    def test_list_is_public_and_newest_first(self):
        self._create_news(title="Older story")
        self._create_news(title="Newer story")
        resp = app.test_client().get("/api/v1/news")
        self.assertEqual(resp.status_code, 200)
        titles = [n["title"] for n in json.loads(resp.data)]
        self.assertLess(
            titles.index("Newer story"), titles.index("Older story"))

    def test_i18n_round_trips(self):
        resp = self._create_news(
            title_i18n={"az": "Başlıq"}, body_i18n={"az": "Mətn"})
        body = json.loads(resp.data)
        self.assertEqual(body["title_i18n"]["az"], "Başlıq")
        self.assertEqual(body["body_i18n"]["az"], "Mətn")

    def _comment(self, client, news_id, body="Great news"):
        return _json(client, "post", "/api/v1/forum/posts",
                     {"body": body, "target_news_id": news_id})

    def test_comment_requires_login(self):
        news_id = json.loads(self._create_news().data)["id"]
        resp = self._comment(app.test_client(), news_id)
        self.assertEqual(resp.status_code, 401)

    def test_comment_starts_pending_and_is_hidden(self):
        news_id = json.loads(self._create_news().data)["id"]
        resp = self._comment(self.client, news_id)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(json.loads(resp.data)["status"], "pending")
        listing = app.test_client().get(
            "/api/v1/forum/posts?news_id=" + news_id)
        self.assertEqual(json.loads(listing.data), [])

    def test_approved_comment_shows_under_its_news_only(self):
        news_id = json.loads(self._create_news().data)["id"]
        other_id = json.loads(self._create_news(title="Other").data)["id"]
        post_id = json.loads(self._comment(
            self.client, news_id, body="Approved comment").data)["id"]
        _json(self.admin_client, "put",
              "/api/v1/forum/posts/{}/status".format(post_id),
              {"status": "approved"})

        under = json.loads(app.test_client().get(
            "/api/v1/forum/posts?news_id=" + news_id).data)
        self.assertEqual([p["body"] for p in under], ["Approved comment"])
        self.assertEqual(under[0]["target_news_title"], "Headline")
        elsewhere = json.loads(app.test_client().get(
            "/api/v1/forum/posts?news_id=" + other_id).data)
        self.assertEqual(elsewhere, [])
        general = json.loads(app.test_client().get(
            "/api/v1/forum/posts").data)
        self.assertNotIn(
            "Approved comment", [p["body"] for p in general])

        news = json.loads(app.test_client().get("/api/v1/news").data)
        counts = {n["id"]: n["comment_count"] for n in news}
        self.assertEqual(counts[news_id], 1)

    def test_moderation_queue_includes_news_comments(self):
        news_id = json.loads(self._create_news().data)["id"]
        body = "Queued comment {}".format(uuid.uuid4())
        self._comment(self.client, news_id, body=body)
        queue = json.loads(self.admin_client.get(
            "/api/v1/forum/posts?status=pending").data)
        queued = [p for p in queue if p["body"] == body]
        self.assertEqual(len(queued), 1)
        self.assertEqual(queued[0]["target_news_title"], "Headline")

    def test_reply_to_a_news_comment_stays_on_the_news(self):
        news_id = json.loads(self._create_news().data)["id"]
        comment = json.loads(_json(
            self.admin_client, "post", "/api/v1/forum/posts",
            {"body": "Top comment", "target_news_id": news_id}).data)
        reply = json.loads(_json(
            self.admin_client, "post", "/api/v1/forum/posts",
            {"body": "A reply", "parent_id": comment["id"]}).data)
        self.assertEqual(reply["target_news_id"], news_id)
        news = json.loads(app.test_client().get("/api/v1/news").data)
        counts = {n["id"]: n["comment_count"] for n in news}
        self.assertEqual(counts[news_id], 2)
        self.admin_client.delete("/api/v1/news/" + news_id)
        self.assertNotIn(
            "ForumPost.{}".format(reply["id"]), storage.all(ForumPost))

    def test_comment_on_missing_news_is_rejected(self):
        resp = self._comment(self.client, "does-not-exist")
        self.assertEqual(resp.status_code, 400)

    def test_comment_cannot_target_city_and_news(self):
        news_id = json.loads(self._create_news().data)["id"]
        resp = _json(self.client, "post", "/api/v1/forum/posts", {
            "body": "Both", "target_news_id": news_id,
            "target_city_id": "x"})
        self.assertEqual(resp.status_code, 400)

    def test_deleting_news_deletes_its_comments(self):
        news_id = json.loads(self._create_news().data)["id"]
        post_id = json.loads(self._comment(self.client, news_id).data)["id"]
        resp = self.admin_client.delete("/api/v1/news/" + news_id)
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(
            "ForumPost.{}".format(post_id), storage.all(ForumPost))
        self.assertEqual(
            self.admin_client.delete("/api/v1/news/" + news_id).status_code,
            404)


class TestFavoritesViews(unittest.TestCase):
    """End-to-end tests for /favorites views."""

    def setUp(self):
        auth_utils.register_limiter._attempts.clear()
        auth_utils.login_limiter._attempts.clear()

        self.client = app.test_client()
        resp = register_and_login(
            self.client, "Favorites User",
            _unique_email(), TEST_PASSWORD)
        self.user_id = json.loads(resp.data)["id"]

        self.admin_client = app.test_client()
        admin = User(name="Test Admin", email=_unique_email(), role="admin")
        admin.set_password(TEST_PASSWORD)
        admin.save()
        self.admin_client.post(
            "/api/v1/auth/login",
            data=json.dumps(
                {"email": admin.email, "password": TEST_PASSWORD}),
            content_type="application/json")

        region = json.loads(self.admin_client.post(
            "/api/v1/regions",
            data=json.dumps({"name": "Region-{}".format(uuid.uuid4())}),
            content_type="application/json").data)
        city = json.loads(self.admin_client.post(
            "/api/v1/regions/{}/cities".format(region["id"]),
            data=json.dumps(
                {"name": "City", "latitude": 39.8, "longitude": 46.75}),
            content_type="application/json").data)
        self.city_id = city["id"]

    def _other_client(self):
        other = app.test_client()
        register_and_login(
            other, "Other User",
            _unique_email(), TEST_PASSWORD)
        return other

    def test_add_requires_login(self):
        anon = app.test_client()
        resp = anon.post(
            "/api/v1/favorites",
            data=json.dumps({"city_id": self.city_id}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 401)

    def test_list_requires_login(self):
        anon = app.test_client()
        resp = anon.get("/api/v1/favorites")
        self.assertEqual(resp.status_code, 401)

    def test_remove_requires_login(self):
        anon = app.test_client()
        resp = anon.delete("/api/v1/favorites/{}".format(self.city_id))
        self.assertEqual(resp.status_code, 401)

    def test_add_and_list_favorite(self):
        resp = self.client.post(
            "/api/v1/favorites",
            data=json.dumps({"city_id": self.city_id}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 201)

        listed = json.loads(self.client.get("/api/v1/favorites").data)
        self.assertEqual([c["id"] for c in listed], [self.city_id])

    def test_add_rejects_nonexistent_city(self):
        resp = self.client.post(
            "/api/v1/favorites",
            data=json.dumps({"city_id": "not-a-real-city-id"}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 400)

    def test_add_rejects_missing_city_id(self):
        resp = self.client.post(
            "/api/v1/favorites",
            data=json.dumps({}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 400)

    def test_add_is_idempotent(self):
        first = self.client.post(
            "/api/v1/favorites",
            data=json.dumps({"city_id": self.city_id}),
            content_type="application/json")
        second = self.client.post(
            "/api/v1/favorites",
            data=json.dumps({"city_id": self.city_id}),
            content_type="application/json")
        self.assertEqual(second.status_code, 200)
        self.assertEqual(
            json.loads(first.data)["id"], json.loads(second.data)["id"])

        listed = json.loads(self.client.get("/api/v1/favorites").data)
        self.assertEqual(len(listed), 1)

    def test_remove_favorite(self):
        self.client.post(
            "/api/v1/favorites",
            data=json.dumps({"city_id": self.city_id}),
            content_type="application/json")
        resp = self.client.delete(
            "/api/v1/favorites/{}".format(self.city_id))
        self.assertEqual(resp.status_code, 200)

        listed = json.loads(self.client.get("/api/v1/favorites").data)
        self.assertEqual(listed, [])

    def test_remove_is_idempotent(self):
        resp = self.client.delete(
            "/api/v1/favorites/{}".format(self.city_id))
        self.assertEqual(resp.status_code, 200)

    def test_favorites_are_per_user(self):
        self.client.post(
            "/api/v1/favorites",
            data=json.dumps({"city_id": self.city_id}),
            content_type="application/json")

        other = self._other_client()
        other_listed = json.loads(other.get("/api/v1/favorites").data)
        self.assertEqual(other_listed, [])

    def test_cannot_remove_another_users_favorite(self):
        self.client.post(
            "/api/v1/favorites",
            data=json.dumps({"city_id": self.city_id}),
            content_type="application/json")

        other = self._other_client()
        other.delete("/api/v1/favorites/{}".format(self.city_id))

        listed = json.loads(self.client.get("/api/v1/favorites").data)
        self.assertEqual([c["id"] for c in listed], [self.city_id])

    def test_deleting_city_removes_favorites_of_it(self):
        self.client.post(
            "/api/v1/favorites",
            data=json.dumps({"city_id": self.city_id}),
            content_type="application/json")
        resp = self.admin_client.delete(
            "/api/v1/cities/{}".format(self.city_id))
        self.assertEqual(resp.status_code, 200)

        listed = json.loads(self.client.get("/api/v1/favorites").data)
        self.assertEqual(listed, [])


class TestImageViews(unittest.TestCase):
    """End-to-end tests for /images views."""

    def setUp(self):
        self.client = app.test_client()
        self.admin_client = app.test_client()
        admin = User(name="Test Admin", email=_unique_email(), role="admin")
        admin.set_password(TEST_PASSWORD)
        admin.save()
        login_resp = self.admin_client.post(
            "/api/v1/auth/login",
            data=json.dumps(
                {"email": admin.email, "password": TEST_PASSWORD}),
            content_type="application/json")
        self.assertEqual(login_resp.status_code, 200)

    def _upload(self, client, data, filename="photo.png"):
        return client.post(
            "/api/v1/images",
            data={"file": (io.BytesIO(data), filename)},
            content_type="multipart/form-data")

    def test_upload_requires_admin_session(self):
        resp = self._upload(self.client, PNG_BYTES)
        self.assertEqual(resp.status_code, 401)

    def test_upload_rejects_non_admin(self):
        user_client = app.test_client()
        register_and_login(
            user_client, "Regular User",
            _unique_email(), TEST_PASSWORD)
        resp = self._upload(user_client, PNG_BYTES)
        self.assertEqual(resp.status_code, 403)

    def test_upload_and_fetch_png(self):
        resp = self._upload(self.admin_client, PNG_BYTES)
        self.assertEqual(resp.status_code, 201)
        url = json.loads(resp.data)["url"]
        self.assertIn("/api/v1/images/", url)
        image_id = url.rsplit("/", 1)[1]

        get_resp = self.client.get("/api/v1/images/{}".format(image_id))
        self.assertEqual(get_resp.status_code, 200)
        self.assertEqual(get_resp.mimetype, "image/png")
        self.assertEqual(get_resp.data, PNG_BYTES)

    def test_upload_jpeg_gif_webp(self):
        cases = [
            (JPEG_BYTES, "image/jpeg"),
            (GIF_BYTES, "image/gif"),
            (WEBP_BYTES, "image/webp"),
        ]
        for data, expected_type in cases:
            resp = self._upload(self.admin_client, data)
            self.assertEqual(resp.status_code, 201)
            url = json.loads(resp.data)["url"]
            image_id = url.rsplit("/", 1)[1]
            get_resp = self.client.get(
                "/api/v1/images/{}".format(image_id))
            self.assertEqual(get_resp.mimetype, expected_type)

    def test_upload_rejects_non_image(self):
        resp = self._upload(
            self.admin_client, b"not an image", filename="photo.png")
        self.assertEqual(resp.status_code, 400)

    def test_upload_requires_file_field(self):
        resp = self.admin_client.post(
            "/api/v1/images", data={}, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 400)

    def test_upload_rejects_oversized_file(self):
        oversized = PNG_BYTES + b"\x00" * (4 * 1024 * 1024)
        resp = self._upload(self.admin_client, oversized)
        self.assertEqual(resp.status_code, 413)

    def test_fetch_unknown_id_is_404(self):
        resp = self.client.get("/api/v1/images/does-not-exist")
        self.assertEqual(resp.status_code, 404)

    def _create_region(self):
        return json.loads(self.admin_client.post(
            "/api/v1/regions",
            data=json.dumps({"name": "Region-{}".format(uuid.uuid4())}),
            content_type="application/json").data)

    def _create_city(self, region_id, **overrides):
        payload = {
            "name": "Place-{}".format(uuid.uuid4()),
            "latitude": 39.8, "longitude": 46.75,
        }
        payload.update(overrides)
        return json.loads(self.admin_client.post(
            "/api/v1/regions/{}/cities".format(region_id),
            data=json.dumps(payload),
            content_type="application/json").data)

    def test_delete_city_deletes_its_uploaded_images(self):
        main_url = json.loads(
            self._upload(self.admin_client, PNG_BYTES).data)["url"]
        before_url = json.loads(
            self._upload(self.admin_client, JPEG_BYTES).data)["url"]
        region = self._create_region()
        city = self._create_city(
            region["id"], image_url=main_url, image_url_before=before_url)

        self.admin_client.delete("/api/v1/cities/{}".format(city["id"]))

        self.assertEqual(self.client.get(_path(main_url)).status_code, 404)
        self.assertEqual(
            self.client.get(_path(before_url)).status_code, 404)

    def test_delete_city_leaves_external_image_url_alone(self):
        region = self._create_region()
        city = self._create_city(
            region["id"], image_url="https://example.com/photo.jpg")
        resp = self.admin_client.delete(
            "/api/v1/cities/{}".format(city["id"]))
        self.assertEqual(resp.status_code, 200)

    def test_replacing_image_url_deletes_old_upload(self):
        old_url = json.loads(
            self._upload(self.admin_client, PNG_BYTES).data)["url"]
        new_url = json.loads(
            self._upload(self.admin_client, JPEG_BYTES).data)["url"]
        region = self._create_region()
        city = self._create_city(region["id"], image_url=old_url)

        self.admin_client.put(
            "/api/v1/cities/{}".format(city["id"]),
            data=json.dumps({"image_url": new_url}),
            content_type="application/json")

        self.assertEqual(self.client.get(_path(old_url)).status_code, 404)
        self.assertEqual(self.client.get(_path(new_url)).status_code, 200)


class TestSharePage(unittest.TestCase):
    """Tests for /p/<city_id> OpenGraph and Twitter card rendering."""

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
        tr = self.client.get(
            "/p/{}?lang=tr".format(city.id)).get_data(as_text=True)
        self.assertIn("Shusha — Dirchalish", tr)
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
    """Tests for /sitemap.xml and /robots.txt."""

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
        city = _make_city()
        city_id = city.id
        city.delete()
        storage.save()
        self.assertEqual(self.client.get("/p/" + city_id).status_code, 404)


class TestContributionTier(unittest.TestCase):
    """Pure boundary tests for contribution_tier()."""

    def test_zero_posts_has_no_tier(self):
        self.assertIsNone(contribution_tier(0))

    def test_below_first_threshold_has_no_tier(self):
        self.assertIsNone(contribution_tier(0))

    def test_newcomer_boundary(self):
        self.assertEqual(contribution_tier(1), "newcomer")
        self.assertEqual(contribution_tier(2), "newcomer")

    def test_contributor_boundary(self):
        self.assertEqual(contribution_tier(3), "contributor")
        self.assertEqual(contribution_tier(9), "contributor")

    def test_local_expert_boundary(self):
        self.assertEqual(contribution_tier(10), "local_expert")
        self.assertEqual(contribution_tier(1000), "local_expert")


class TestApprovedPostCount(unittest.TestCase):
    """approved_post_count() only counts a given user's own approved posts."""

    def setUp(self):
        self.user = User(name="Counter", email=_unique_email(), role="user")
        self.user.set_password(TEST_PASSWORD)
        self.user.save()
        self.other = User(name="Other", email=_unique_email(), role="user")
        self.other.set_password(TEST_PASSWORD)
        self.other.save()

    def test_counts_only_approved(self):
        _make_post(self.user.id, status="approved")
        _make_post(self.user.id, status="pending")
        _make_post(self.user.id, status="rejected")
        self.assertEqual(approved_post_count(self.user.id), 1)

    def test_ignores_other_users(self):
        _make_post(self.user.id, status="approved")
        _make_post(self.other.id, status="approved")
        _make_post(self.other.id, status="approved")
        self.assertEqual(approved_post_count(self.user.id), 1)
        self.assertEqual(approved_post_count(self.other.id), 2)

    def test_zero_for_a_user_with_no_posts(self):
        self.assertEqual(approved_post_count(self.user.id), 0)


class TestContributionsInApiResponses(unittest.TestCase):
    """End-to-end: contribution_count/contribution_tier in API responses."""

    def setUp(self):
        self.client = app.test_client()
        self.email = _unique_email()
        resp = register_and_login(
            self.client, "Tiered User",
            self.email, TEST_PASSWORD)
        self.user_id = json.loads(resp.data)["id"]

    def test_me_has_no_tier_with_zero_posts(self):
        resp = self.client.get("/api/v1/auth/me")
        data = json.loads(resp.data)
        self.assertEqual(data["contribution_count"], 0)
        self.assertIsNone(data["contribution_tier"])

    def test_me_reflects_approved_post_count(self):
        for _ in range(3):
            _make_post(self.user_id, status="approved")
        resp = self.client.get("/api/v1/auth/me")
        data = json.loads(resp.data)
        self.assertEqual(data["contribution_count"], 3)
        self.assertEqual(data["contribution_tier"], "contributor")

    def test_pending_posts_dont_count_toward_me(self):
        _make_post(self.user_id, status="pending")
        resp = self.client.get("/api/v1/auth/me")
        data = json.loads(resp.data)
        self.assertEqual(data["contribution_count"], 0)
        self.assertIsNone(data["contribution_tier"])

    def test_forum_feed_includes_author_tier(self):
        for _ in range(3):
            _make_post(self.user_id, status="approved")
        resp = self.client.get("/api/v1/forum/posts")
        posts = json.loads(resp.data)
        own_posts = [p for p in posts if p["author_id"] == self.user_id]
        self.assertEqual(len(own_posts), 3)
        for post in own_posts:
            self.assertEqual(post["author_tier"], "contributor")


if __name__ == "__main__":
    unittest.main()

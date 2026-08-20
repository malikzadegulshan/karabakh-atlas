#!/usr/bin/python3
"""Smoke tests for the API v1 views, using Flask's test client."""
import json
import unittest
import uuid
from api.v1.app import app
from models.user import User

TEST_PASSWORD = "correcthorsebattery"


class TestAPIViews(unittest.TestCase):
    """End-to-end tests against the Flask test client."""

    def setUp(self):
        """Create a test client, logged in as a fresh admin user.

        Region/city writes require an admin session, so every test
        below that creates/updates/deletes data rides on this login.
        """
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

        # Admin posts are auto-approved (see api/v1/views/forum.py).
        self.client.post(
            "/api/v1/forum/posts",
            data=json.dumps(
                {"body": "Nice place", "target_city_id": city["id"]}),
            content_type="application/json")

        after = json.loads(self.client.get("/api/v1/stats").data)
        self.assertEqual(after["forum_posts"], before["forum_posts"] + 1)

    def test_stats_excludes_pending_forum_posts(self):
        regular = app.test_client()
        regular.post(
            "/api/v1/auth/register",
            data=json.dumps({
                "name": "Regular User",
                "email": "regular-{}@example.com".format(uuid.uuid4()),
                "password": TEST_PASSWORD}),
            content_type="application/json")
        before = json.loads(self.client.get("/api/v1/stats").data)

        # A non-admin's post starts "pending" — not publicly visible.
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
        """A PUT with category explicitly set to null is rejected, not
        silently applied — optional_enum() treats None as "field
        omitted" for genuinely optional fields, but category always
        needs a real value (see the comment in _validate_city_data)."""
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
        """POST /api/v1/regions without a name is rejected with 400."""
        response = self.client.post(
            "/api/v1/regions",
            data=json.dumps({}),
            content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_create_region_rejects_blank_name(self):
        """POST /api/v1/regions with a blank/whitespace name is rejected."""
        response = self.client.post(
            "/api/v1/regions",
            data=json.dumps({"name": "   "}),
            content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_create_city_rejects_out_of_range_latitude(self):
        """POST .../cities with an out-of-range latitude is rejected."""
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
        """POST .../cities with a string latitude is rejected."""
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
        """POST .../cities without a category defaults it to "city"."""
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
        """POST .../cities accepts a point-of-interest category."""
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
        """POST .../cities accepts and stores phone/website."""
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
        """POST .../cities with a too-long phone is rejected with 400."""
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
        """POST .../cities rejects a javascript: URL in website — the
        frontend renders this field straight into an <a href="...">,
        so an unvalidated scheme here is a stored-XSS vector against
        every visitor who views the place, not just whoever set it."""
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
        """POST .../cities rejects a javascript: URL in image_url too."""
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

    def test_create_city_accepts_road_category(self):
        """POST .../cities accepts the "road" category."""
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
        """POST .../cities with an unrecognized category is rejected."""
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
        """Deleting a region also deletes the cities that belong to it."""
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
        """A region can be created, then a city nested under it."""
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
        """GET /api/v1/cities/<bad-id> returns 404."""
        response = self.client.get("/api/v1/cities/does-not-exist")
        self.assertEqual(response.status_code, 404)

    def test_create_region_rejects_client_supplied_id(self):
        """POST /api/v1/regions with an "id" field is rejected outright,
        so it can never collide with (and overwrite) an existing region."""
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
        """POST .../cities with an "id" field is rejected outright, so it
        can never collide with (and overwrite) an existing city."""
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
        """Writes are rejected with no session; GET stays open regardless."""
        anon_client = app.test_client()
        no_login_resp = anon_client.post(
            "/api/v1/regions",
            data=json.dumps({"name": "Should Fail"}),
            content_type="application/json")
        self.assertEqual(no_login_resp.status_code, 401)

        get_resp = anon_client.get("/api/v1/regions")
        self.assertEqual(get_resp.status_code, 200)

    def test_write_requires_admin_role_not_just_login(self):
        """A logged-in non-admin user still can't write regions/cities."""
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


if __name__ == "__main__":
    unittest.main()

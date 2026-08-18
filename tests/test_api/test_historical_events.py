#!/usr/bin/python3
"""Tests for the /historical-events views: public reads, admin-gated
writes, and validation (particularly the year floor tied to how far
back the timeline's own imagery reaches)."""
import json
import unittest
import uuid
from datetime import datetime
from api.v1.app import app
from models.user import User

TEST_PASSWORD = "correcthorsebattery"
CURRENT_YEAR = datetime.utcnow().year


class TestHistoricalEventViews(unittest.TestCase):
    """End-to-end tests against the Flask test client."""

    def setUp(self):
        """Create a test client, logged in as a fresh admin user."""
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
        """Posting without a session is rejected with 401."""
        anon = app.test_client()
        resp = anon.post(
            "/api/v1/historical-events",
            data=json.dumps({
                "title": "X", "year": 2020, "latitude": 1, "longitude": 1,
            }),
            content_type="application/json")
        self.assertEqual(resp.status_code, 401)

    def test_create_rejects_non_admin(self):
        """A logged-in non-admin can't create an event."""
        user_client = app.test_client()
        user_client.post(
            "/api/v1/auth/register",
            data=json.dumps({
                "name": "Regular User",
                "email": "user-{}@example.com".format(uuid.uuid4()),
                "password": TEST_PASSWORD}),
            content_type="application/json")
        resp = user_client.post(
            "/api/v1/historical-events",
            data=json.dumps({
                "title": "X", "year": 2020, "latitude": 1, "longitude": 1,
            }),
            content_type="application/json")
        self.assertEqual(resp.status_code, 403)

    def test_create_succeeds_for_admin(self):
        """An admin can create a historical event."""
        resp = self._create_event()
        self.assertEqual(resp.status_code, 201)
        body = json.loads(resp.data)
        self.assertEqual(body["title"], "Sample Event")
        self.assertEqual(body["year"], 2020)

    def test_create_rejects_year_before_imagery_floor(self):
        """A year older than the timeline's own imagery is rejected."""
        resp = self._create_event(year=1994)
        self.assertEqual(resp.status_code, 400)

    def test_create_rejects_year_in_the_future(self):
        """A year beyond the current one is rejected."""
        resp = self._create_event(year=CURRENT_YEAR + 5)
        self.assertEqual(resp.status_code, 400)

    def test_create_rejects_non_integer_year(self):
        """A fractional year is rejected."""
        resp = self._create_event(year=2020.5)
        self.assertEqual(resp.status_code, 400)

    def test_create_rejects_blank_title(self):
        """A blank/whitespace-only title is rejected."""
        resp = self._create_event(title="   ")
        self.assertEqual(resp.status_code, 400)

    def test_create_rejects_out_of_range_latitude(self):
        """An out-of-range latitude is rejected."""
        resp = self._create_event(latitude=999)
        self.assertEqual(resp.status_code, 400)

    def test_create_rejects_javascript_scheme_source_url(self):
        """A javascript: source_url is rejected."""
        resp = self._create_event(source_url="javascript:alert(1)")
        self.assertEqual(resp.status_code, 400)

    def test_list_is_publicly_readable(self):
        """GET /historical-events works without a session."""
        self._create_event(title="Public Event")
        anon = app.test_client()
        resp = anon.get("/api/v1/historical-events")
        self.assertEqual(resp.status_code, 200)
        titles = [e["title"] for e in json.loads(resp.data)]
        self.assertIn("Public Event", titles)

    def test_list_sorted_by_year(self):
        """The list comes back sorted oldest year first."""
        self._create_event(title="Later", year=2022)
        self._create_event(title="Earlier", year=2016)
        resp = self.client.get("/api/v1/historical-events")
        titles = [e["title"] for e in json.loads(resp.data)]
        self.assertLess(titles.index("Earlier"), titles.index("Later"))

    def test_update_requires_admin(self):
        """PUT without a session is rejected with 401."""
        create_resp = self._create_event()
        event_id = json.loads(create_resp.data)["id"]
        anon = app.test_client()
        resp = anon.put(
            "/api/v1/historical-events/{}".format(event_id),
            data=json.dumps({"title": "Renamed"}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 401)

    def test_update_succeeds_for_admin(self):
        """An admin can update an existing event."""
        create_resp = self._create_event()
        event_id = json.loads(create_resp.data)["id"]
        resp = self.client.put(
            "/api/v1/historical-events/{}".format(event_id),
            data=json.dumps({"title": "Renamed"}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(json.loads(resp.data)["title"], "Renamed")

    def test_update_missing_event_returns_404(self):
        """PUT on a nonexistent id returns 404."""
        resp = self.client.put(
            "/api/v1/historical-events/does-not-exist",
            data=json.dumps({"title": "Renamed"}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 404)

    def test_delete_requires_admin(self):
        """DELETE without a session is rejected with 401."""
        create_resp = self._create_event()
        event_id = json.loads(create_resp.data)["id"]
        anon = app.test_client()
        resp = anon.delete("/api/v1/historical-events/{}".format(event_id))
        self.assertEqual(resp.status_code, 401)

    def test_delete_succeeds_for_admin(self):
        """An admin can delete an event."""
        create_resp = self._create_event()
        event_id = json.loads(create_resp.data)["id"]
        resp = self.client.delete(
            "/api/v1/historical-events/{}".format(event_id))
        self.assertEqual(resp.status_code, 200)
        get_resp = self.client.get("/api/v1/historical-events")
        ids = [e["id"] for e in json.loads(get_resp.data)]
        self.assertNotIn(event_id, ids)


if __name__ == "__main__":
    unittest.main()

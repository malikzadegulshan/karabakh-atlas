#!/usr/bin/python3
"""Smoke tests for the API v1 views, using Flask's test client."""
import json
import os
import unittest
from api.v1.app import app


class TestAPIViews(unittest.TestCase):
    """End-to-end tests against the Flask test client."""

    def setUp(self):
        """Create a test client for each test."""
        self.client = app.test_client()

    def test_status(self):
        """GET /api/v1/status returns OK."""
        response = self.client.get("/api/v1/status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.data), {"status": "OK"})

    def test_create_region_requires_name(self):
        """POST /api/v1/regions without a name is rejected with 400."""
        response = self.client.post(
            "/api/v1/regions",
            data=json.dumps({}),
            content_type="application/json")
        self.assertEqual(response.status_code, 400)

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

    def test_write_requires_api_key_when_configured(self):
        """Writes need X-API-Key once KBA_API_KEY is set; GET stays open."""
        os.environ["KBA_API_KEY"] = "testkey123"
        try:
            no_key_resp = self.client.post(
                "/api/v1/regions",
                data=json.dumps({"name": "Should Fail"}),
                content_type="application/json")
            self.assertEqual(no_key_resp.status_code, 401)

            wrong_key_resp = self.client.post(
                "/api/v1/regions",
                data=json.dumps({"name": "Should Fail"}),
                content_type="application/json",
                headers={"X-API-Key": "wrong"})
            self.assertEqual(wrong_key_resp.status_code, 401)

            with_key_resp = self.client.post(
                "/api/v1/regions",
                data=json.dumps({"name": "Should Succeed"}),
                content_type="application/json",
                headers={"X-API-Key": "testkey123"})
            self.assertEqual(with_key_resp.status_code, 201)

            get_resp = self.client.get("/api/v1/regions")
            self.assertEqual(get_resp.status_code, 200)
        finally:
            del os.environ["KBA_API_KEY"]


if __name__ == "__main__":
    unittest.main()

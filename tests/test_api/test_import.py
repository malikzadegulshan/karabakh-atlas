#!/usr/bin/python3
"""Tests for the bulk place import: POST /regions/<id>/cities/import."""
import json
import unittest
import uuid
from api.v1.app import app
from models import storage
from models.city import City
from models.user import User

PASSWORD = "correcthorsebattery"


def _email():
    return "user-{}@example.com".format(uuid.uuid4())


def _post(client, url, payload):
    return client.post(
        url, data=json.dumps(payload), content_type="application/json")


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

    # -- Preview vs import -----------------------------------------

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

    # -- Validation (same rules as adding a place by hand) ---------

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

    # -- Duplicates -------------------------------------------------

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
        """The existing "Khankendi" has az "Xankəndi"; a CSV row named
        "Xankəndi" is that same city."""
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

    # -- Limits and access -----------------------------------------

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
        _post(user, "/api/v1/auth/register", {
            "name": "Reader", "email": _email(), "password": PASSWORD})
        self.assertEqual(self._import(rows, client=user).status_code, 403)
        self.assertEqual(self._cities(), [])


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/python3
"""Tests for the /images views: upload (admin-gated, format/size
validated by sniffing the file's own bytes) and public retrieval."""
import io
import json
import unittest
import uuid
from api.v1.app import app
from models.user import User

TEST_PASSWORD = "correcthorsebattery"

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG_BYTES = b"\xff\xd8\xff" + b"\x00" * 32
GIF_BYTES = b"GIF89a" + b"\x00" * 32
WEBP_BYTES = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 32


def _unique_email():
    return "images-admin-{}@example.com".format(uuid.uuid4())


def _path(absolute_url):
    """Strip an image URL's host, since the test client takes paths."""
    return "/api/v1" + absolute_url.split("/api/v1")[1]


class TestImageViews(unittest.TestCase):
    """End-to-end tests against the Flask test client."""

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
        """An anonymous request is rejected with 401."""
        resp = self._upload(self.client, PNG_BYTES)
        self.assertEqual(resp.status_code, 401)

    def test_upload_rejects_non_admin(self):
        """A logged-in non-admin can't upload."""
        user_client = app.test_client()
        user_client.post(
            "/api/v1/auth/register",
            data=json.dumps({
                "name": "Regular User", "email": _unique_email(),
                "password": TEST_PASSWORD}),
            content_type="application/json")
        resp = self._upload(user_client, PNG_BYTES)
        self.assertEqual(resp.status_code, 403)

    def test_upload_and_fetch_png(self):
        """A valid PNG upload round-trips through GET /images/<id>."""
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
        """Every supported format is sniffed to the right content type."""
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
        """A file whose bytes don't match a known image signature is
        rejected regardless of its filename or declared content type."""
        resp = self._upload(
            self.admin_client, b"not an image", filename="photo.png")
        self.assertEqual(resp.status_code, 400)

    def test_upload_requires_file_field(self):
        """A request with no file part at all is rejected."""
        resp = self.admin_client.post(
            "/api/v1/images", data={}, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 400)

    def test_upload_rejects_oversized_file(self):
        """A file over the 4MB cap is rejected with 413."""
        oversized = PNG_BYTES + b"\x00" * (4 * 1024 * 1024)
        resp = self._upload(self.admin_client, oversized)
        self.assertEqual(resp.status_code, 413)

    def test_fetch_unknown_id_is_404(self):
        """Fetching a nonexistent image id returns 404, not a crash."""
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
        """Deleting a place also drops the Image rows its own uploaded
        photos point at — mirrors the existing forum-post/favorite
        cascade in delete_city()."""
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
        """A pasted external image_url isn't ours to delete, so it's
        left untouched (there's nothing to assert it deleted — this
        just confirms deleting the city doesn't error on a non-upload
        URL)."""
        region = self._create_region()
        city = self._create_city(
            region["id"], image_url="https://example.com/photo.jpg")
        resp = self.admin_client.delete(
            "/api/v1/cities/{}".format(city["id"]))
        self.assertEqual(resp.status_code, 200)

    def test_replacing_image_url_deletes_old_upload(self):
        """Uploading a new photo over an old one on the same place
        drops the now-unreferenced Image row instead of leaking it."""
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

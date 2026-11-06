#!/usr/bin/python3
"""Image upload endpoint: lets the admin panel attach an uploaded photo
to a place instead of only pasting an external image URL. Returns a
URL that goes straight into City.image_url/image_url_before — the
same field a pasted URL fills — so nothing downstream needs to know
which path a given image came from.
"""
import base64
import binascii
import os
from flask import jsonify, abort, request, Response
from api.v1.views import app_views
from api.v1.auth_utils import get_current_user, image_upload_limiter
from models import storage
from models.image import Image

# Sniffed from the file's own bytes, never trusted from the
# client-supplied Content-Type header or filename extension (either
# one is trivial to fake).
_SIGNATURES = (
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
)

MAX_IMAGE_BYTES = 4 * 1024 * 1024


def _sniff_content_type(head):
    """Return the image/* MIME type head's magic bytes match, or None."""
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    for signature, content_type in _SIGNATURES:
        if head.startswith(signature):
            return content_type
    return None


@app_views.route("/images", methods=["POST"])
def upload_image():
    """Accept one multipart image upload, return its retrieval URL."""
    user = get_current_user()
    rate_key = user.id if user else (request.remote_addr or "unknown")
    if image_upload_limiter.is_limited(rate_key):
        return jsonify({
            "error": "Too many image uploads. Try again later.",
        }), 429
    upload = request.files.get("file")
    if upload is None or upload.filename == "":
        abort(400, description="file is required")
    data = upload.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        abort(413, description="Image must be at most 4MB")
    content_type = _sniff_content_type(data[:12])
    if content_type is None:
        abort(
            400,
            description="File must be a JPEG, PNG, GIF, or WebP image")
    image = Image(
        content_type=content_type,
        data_base64=base64.b64encode(data).decode("ascii"))
    image.save()
    image_upload_limiter.record(rate_key)
    public_base = os.environ.get("KBA_PUBLIC_URL", "").strip().rstrip("/")
    base_url = (public_base + "/") if public_base else request.host_url
    url = "{}api/v1/images/{}".format(base_url, image.id)
    return jsonify({"url": url}), 201


@app_views.route("/images/<image_id>", methods=["GET"])
def get_image(image_id):
    """Serve a previously uploaded image's raw bytes."""
    image = storage.all(Image).get("Image.{}".format(image_id))
    if image is None:
        abort(404)
    try:
        data = base64.b64decode(image.data_base64)
    except (binascii.Error, ValueError):
        abort(404)
    return Response(
        data,
        mimetype=image.content_type,
        # Content-addressed by an opaque id that's never reused for
        # different bytes, so caching it forever is safe.
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )

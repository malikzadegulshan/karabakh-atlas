#!/usr/bin/python3
"""Starts the Flask API application for the Karabakh Atlas backend."""
import os
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_swagger_ui import get_swaggerui_blueprint
from models import storage
from api.v1.views import app_views

WRITE_METHODS = {"POST", "PUT", "DELETE"}
OPENAPI_SPEC_PATH = "/api/v1/openapi.yaml"
SWAGGER_UI_PATH = "/api/docs"

app = Flask(__name__)
app.url_map.strict_slashes = False
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024
app.register_blueprint(app_views)
app.register_blueprint(
    get_swaggerui_blueprint(
        SWAGGER_UI_PATH,
        OPENAPI_SPEC_PATH,
        config={"app_name": "Karabakh Atlas API"},
    ),
    url_prefix=SWAGGER_UI_PATH,
)
CORS(app, resources={r"/api/v1/*": {"origins": "*"}})

if os.environ.get("KBA_AUTO_SEED") == "true":
    # Off by default (local dev is unaffected); hosting platforms without
    # guaranteed shell access to run seed_data.py manually after deploy
    # can set this instead. get_or_create_* in seed_data.py is
    # idempotent, so re-running it on every worker boot is harmless.
    import seed_data
    seed_data.seed()


@app.route(OPENAPI_SPEC_PATH)
def openapi_spec():
    """Serve the static OpenAPI spec backing the Swagger UI at /api/docs."""
    return send_from_directory(
        os.path.dirname(__file__), "openapi.yaml",
        mimetype="application/yaml")


@app.before_request
def require_api_key_for_writes():
    """Reject write requests missing X-API-Key, if KBA_API_KEY is set.

    Read-only GET requests are always allowed. When KBA_API_KEY isn't
    configured (the default for local dev), writes stay open too.
    """
    api_key = os.environ.get("KBA_API_KEY")
    if not api_key or request.method not in WRITE_METHODS:
        return None
    if request.headers.get("X-API-Key") != api_key:
        return jsonify({"error": "Unauthorized"}), 401


@app.teardown_appcontext
def teardown_storage(exception):
    """Close the storage session at the end of each request."""
    storage.close()


@app.errorhandler(400)
def bad_request(error):
    """Return a JSON 400 response instead of Flask's default HTML page."""
    message = getattr(error, "description", "Bad request")
    return jsonify({"error": message}), 400


@app.errorhandler(404)
def not_found(error):
    """Return a JSON 404 response instead of Flask's default HTML page."""
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(413)
def payload_too_large(error):
    """Return a JSON 413 response instead of Flask's default HTML page."""
    return jsonify({"error": "Payload too large"}), 413


if __name__ == "__main__":
    host = os.environ.get("KBA_API_HOST", "0.0.0.0")
    port = int(os.environ.get("KBA_API_PORT", "5000"))
    app.run(host=host, port=port, threaded=True)

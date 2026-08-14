#!/usr/bin/python3
"""Starts the Flask API application for the Karabakh Atlas backend."""
import os
import secrets
import sys
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_swagger_ui import get_swaggerui_blueprint
from models import storage
from models.user import User
from api.v1.views import app_views
from api.v1.auth_utils import get_current_user

WRITE_METHODS = {"POST", "PUT", "DELETE"}
# Only region/city writes go through the account gate — /auth/* has its
# own rules (register/login must be reachable while logged out).
ADMIN_GATED_PREFIXES = ("/api/v1/regions", "/api/v1/cities")
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

app.secret_key = os.environ.get("KBA_SECRET_KEY")
if not app.secret_key:
    if os.environ.get("KBA_ENV") == "test":
        app.secret_key = "test-only-secret-key"
    else:
        # Ephemeral: a new random key each process start invalidates
        # every existing session, and with multiple worker processes
        # (e.g. gunicorn -w 2) each one would sign with a *different*
        # key, breaking sessions unpredictably depending on which
        # worker handles a given request. Fine for a single local dev
        # process; any real deployment must set KBA_SECRET_KEY.
        app.secret_key = secrets.token_hex(32)
        print(
            "WARNING: KBA_SECRET_KEY is not set — using a random, "
            "process-local secret key. Sessions will not survive a "
            "restart and will break across multiple worker processes. "
            "Set KBA_SECRET_KEY for anything beyond local dev.",
            file=sys.stderr,
        )

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE=os.environ.get("KBA_COOKIE_SAMESITE", "Lax"),
    SESSION_COOKIE_SECURE=(
        os.environ.get("KBA_COOKIE_SECURE", "false").lower() == "true"
    ),
)

# Credentialed requests (cookies) can't use a wildcard origin — browsers
# reject that combination outright. Defaults to the local dev frontend;
# a real deployment must set KBA_FRONTEND_ORIGIN to its actual frontend.
# URL(s) (comma-separated for more than one).
_frontend_origins = [
    origin.strip() for origin in os.environ.get(
        "KBA_FRONTEND_ORIGIN", "http://localhost:8000,http://127.0.0.1:8000"
    ).split(",") if origin.strip()
]
CORS(
    app,
    resources={r"/api/v1/*": {"origins": _frontend_origins}},
    supports_credentials=True,
)


def _bootstrap_admin():
    """Create the first admin account from KBA_ADMIN_* env vars, if set
    and no user with that email exists yet.

    These are runtime-only secrets (same convention as .env for local
    dev, or a platform's own secret env vars in production) — never
    committed to git, and this is idempotent so it's safe to leave set
    across restarts.
    """
    email = os.environ.get("KBA_ADMIN_EMAIL")
    password = os.environ.get("KBA_ADMIN_PASSWORD")
    if not email or not password:
        return
    email = email.strip().lower()
    for existing in storage.all(User).values():
        if existing.email.lower() == email:
            return
    admin = User(
        name=os.environ.get("KBA_ADMIN_NAME", "Admin").strip(),
        email=email,
        role="admin",
        # Trusted by construction — whoever set these env vars controls
        # the server itself, so there's no separate identity to verify.
        email_verified=True,
    )
    admin.set_password(password)
    admin.save()


_bootstrap_admin()

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
def require_admin_for_writes():
    """Reject region/city write requests unless the session user is an
    admin. Read-only GET requests, and every /auth/* route (which has
    its own logged-out-friendly rules), are always allowed through.
    """
    if request.method not in WRITE_METHODS:
        return None
    if not request.path.startswith(ADMIN_GATED_PREFIXES):
        return None
    user = get_current_user()
    if user is None:
        return jsonify({"error": "Login required"}), 401
    if user.role != "admin":
        return jsonify({"error": "Admin privileges required"}), 403


@app.after_request
def set_security_headers(response):
    """Attach standard defense-in-depth headers to every response.

    None of these are a substitute for actually validating input (see
    optional_url() in api/v1/validation.py) — they're a second layer,
    e.g. so a future rendering bug can't be leveraged past this API's
    own HTML surface (currently just the self-hosted Swagger UI at
    /api/docs; this file itself only ever returns JSON).
    """
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        # This header is set on every response, including the JSON ones
        # (script-src is inert there regardless — a browser never
        # executes a JSON response body as script no matter what this
        # header says). The 'unsafe-inline' below only actually matters
        # on /api/docs: flask-swagger-ui's bundled template bootstraps
        # itself with an inline <script>, and that page is static
        # vendored boilerplate, not rendering any request data — so
        # permitting inline script there isn't reopening the XSS class
        # this policy exists to backstop everywhere else.
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "frame-ancestors 'none'; "
        "base-uri 'none'"
    )
    return response


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

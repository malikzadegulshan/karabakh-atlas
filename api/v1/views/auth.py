#!/usr/bin/python3
"""Authentication views: register, login, logout, current user, and
email verification."""
import logging
import os
from flask import jsonify, abort, request, session
from api.v1.views import app_views
from api.v1.auth_utils import (
    get_current_user,
    is_login_rate_limited,
    record_login_failure,
    clear_login_failures,
    resend_verification_limiter,
    register_limiter,
)
from api.v1.mailer import send_email
from api.v1.validation import (
    ValidationError,
    require_non_empty_string,
    require_email,
    require_password,
    only_allowed_fields,
)
from models import storage
from models.user import User

REGISTER_FIELDS = {"name", "email", "password"}
LOGIN_FIELDS = {"email", "password"}
VERIFY_FIELDS = {"token"}

logger = logging.getLogger(__name__)


def _find_user_by_email(email):
    email = email.strip().lower()
    for user in storage.all(User).values():
        if user.email.lower() == email:
            return user
    return None


def _frontend_origin():
    origins = os.environ.get(
        "KBA_FRONTEND_ORIGIN", "http://localhost:8000").split(",")
    return origins[0].strip()


def _send_verification_email(user):
    token = user.generate_verification_token()
    user.save()
    link = "{}/index.html?verify={}".format(_frontend_origin(), token)
    send_email(
        user.email,
        "Verify your Karabakh Atlas account",
        "Hi {},\n\n"
        "Confirm your email address by opening this link:\n{}\n\n"
        "This link expires in 24 hours. If you didn't create this "
        "account, you can ignore this email.".format(user.name, link),
    )


@app_views.route("/auth/register", methods=["POST"])
def register():
    """Create a new user account (role "user") and log them in.

    The account works immediately (email verification isn't required to
    use the site) — it just starts unverified, with a verification email
    sent in the background.
    """
    if register_limiter.is_limited(request.remote_addr):
        logger.warning(
            "Registration rate limit hit for %s", request.remote_addr)
        return jsonify({
            "error": "Too many accounts created recently. Try again later.",
        }), 429

    data = request.get_json(silent=True)
    if data is None:
        abort(400, description="Not a JSON")
    try:
        only_allowed_fields(data, REGISTER_FIELDS)
        require_non_empty_string(data, "name")
        require_email(data)
        require_password(data)
    except ValidationError as error:
        abort(400, description=error.message)

    register_limiter.record(request.remote_addr)
    email = data["email"].strip().lower()
    if _find_user_by_email(email) is not None:
        return jsonify(
            {"error": "An account with this email already exists"}), 409

    user = User(
        name=data["name"].strip(), email=email, role="user",
        email_verified=False)
    user.set_password(data["password"])
    user.save()
    _send_verification_email(user)

    session.clear()
    session["user_id"] = user.id
    return jsonify(user.public_dict()), 201


@app_views.route("/auth/login", methods=["POST"])
def login():
    """Log in with email + password, starting a session cookie."""
    data = request.get_json(silent=True)
    if data is None:
        abort(400, description="Not a JSON")
    try:
        only_allowed_fields(data, LOGIN_FIELDS)
        require_non_empty_string(data, "email", max_length=254)
        require_non_empty_string(data, "password", max_length=128)
    except ValidationError as error:
        abort(400, description=error.message)

    email = data["email"].strip().lower()
    rate_key = "{}:{}".format(request.remote_addr, email)
    if is_login_rate_limited(rate_key):
        logger.warning("Login rate limit hit for %s", rate_key)
        return jsonify({
            "error": "Too many failed login attempts. Try again later.",
        }), 429

    user = _find_user_by_email(email)
    if user is None or not user.check_password(data["password"]):
        record_login_failure(rate_key)
        logger.warning("Failed login attempt for %s", rate_key)
        # Same message either way — don't reveal whether the email is
        # registered at all.
        return jsonify({"error": "Invalid email or password"}), 401

    clear_login_failures(rate_key)
    session.clear()
    session["user_id"] = user.id
    return jsonify(user.public_dict()), 200


@app_views.route("/auth/logout", methods=["POST"])
def logout():
    """Clear the current session."""
    session.clear()
    return jsonify({}), 200


@app_views.route("/auth/me", methods=["GET"])
def me():
    """Return the current logged-in user, or 401 if not logged in."""
    user = get_current_user()
    if user is None:
        return jsonify({"error": "Not logged in"}), 401
    return jsonify(user.public_dict()), 200


@app_views.route("/auth/verify", methods=["POST"])
def verify_email():
    """Confirm an email address using the token from the verification
    email. Doesn't require being logged in as that user — possessing
    the token (from the user's own inbox) is the proof of ownership.
    """
    data = request.get_json(silent=True)
    if data is None:
        abort(400, description="Not a JSON")
    try:
        only_allowed_fields(data, VERIFY_FIELDS)
        require_non_empty_string(data, "token", max_length=128)
    except ValidationError as error:
        abort(400, description=error.message)

    token = data["token"]
    for user in storage.all(User).values():
        if user.verification_token == token:
            if not user.consume_verification_token(token):
                return jsonify({"error": "Verification link expired"}), 400
            user.save()
            return jsonify(user.public_dict()), 200
    return jsonify({"error": "Invalid verification link"}), 400


@app_views.route("/auth/resend-verification", methods=["POST"])
def resend_verification():
    """Send a fresh verification email to the logged-in user."""
    user = get_current_user()
    if user is None:
        return jsonify({"error": "Login required"}), 401
    if user.email_verified:
        return jsonify({"error": "Email is already verified"}), 400
    if resend_verification_limiter.is_limited(user.id):
        logger.warning(
            "Resend-verification rate limit hit for user %s", user.id)
        return jsonify({
            "error": "Too many verification emails sent. Try again later.",
        }), 429
    resend_verification_limiter.record(user.id)
    _send_verification_email(user)
    return jsonify({}), 200

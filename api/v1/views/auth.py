#!/usr/bin/python3
"""Authentication views: register, login, logout, and current user."""
from flask import jsonify, abort, request, session
from api.v1.views import app_views
from api.v1.auth_utils import (
    get_current_user,
    is_login_rate_limited,
    record_login_failure,
    clear_login_failures,
)
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


def _find_user_by_email(email):
    email = email.strip().lower()
    for user in storage.all(User).values():
        if user.email.lower() == email:
            return user
    return None


@app_views.route("/auth/register", methods=["POST"])
def register():
    """Create a new user account (role "user") and log them in."""
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

    email = data["email"].strip().lower()
    if _find_user_by_email(email) is not None:
        return jsonify(
            {"error": "An account with this email already exists"}), 409

    user = User(name=data["name"].strip(), email=email, role="user")
    user.set_password(data["password"])
    user.save()

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
        return jsonify({
            "error": "Too many failed login attempts. Try again later.",
        }), 429

    user = _find_user_by_email(email)
    if user is None or not user.check_password(data["password"]):
        record_login_failure(rate_key)
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

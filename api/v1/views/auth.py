#!/usr/bin/python3
"""Authentication views: register, login, logout, current user, and
email verification."""
import logging
from flask import jsonify, abort, request, session
from werkzeug.security import generate_password_hash, check_password_hash
from api.v1.views import app_views
from api.v1.auth_utils import (
    get_current_user,
    login_required,
    log_in,
    is_login_rate_limited,
    record_login_failure,
    clear_login_failures,
    register_limiter,
    password_reset_request_limiter,
    password_reset_attempt_limiter,
)
from api.v1.contributions import approved_post_count, contribution_tier
from api.v1.mailer import (
    SUPPORTED_LANGS,
    build_password_reset_email,
    normalize_lang,
    send_email,
)
from api.v1.validation import (
    ValidationError,
    optional_enum,
    require_non_empty_string,
    require_safe_name,
    require_safe_text,
    require_email,
    require_password,
    only_allowed_fields,
)
from api.v1.forum_utils import delete_forum_posts
from models import storage
from models.favorite import Favorite
from models.forum_post import ForumPost
from models.post_report import PostReport
from models.user import User

REGISTER_FIELDS = {"name", "email", "password", "join_reason", "lang"}
LOGIN_FIELDS = {"email", "password"}
FORGOT_PASSWORD_FIELDS = {"email", "lang"}
RESET_PASSWORD_FIELDS = {"email", "otp", "password"}

MAX_JOIN_REASON_LENGTH = 500
_DUMMY_PASSWORD_HASH = generate_password_hash("kba-timing-guard-password")

logger = logging.getLogger(__name__)


def _find_user_by_email(email):
    email = email.strip().lower()
    for user in storage.all(User).values():
        if user.email.lower() == email:
            return user
    return None


def _serialize_user(user):
    """A user's own public_dict(), plus their contribution tier — every
    response in this file is "here's the logged-in user themselves",
    never another user's profile, so this is always the right amount
    of detail to include."""
    data = user.public_dict()
    count = approved_post_count(user.id)
    data["contribution_count"] = count
    data["contribution_tier"] = contribution_tier(count)
    return data


def _send_password_reset_email(user, otp, lang=None):
    target_lang = normalize_lang(lang or getattr(user, "lang", None))
    subject, text_body, html_body = build_password_reset_email(
        user.name, otp, lang=target_lang
    )
    send_email(user.email, subject, text_body, html_body=html_body)


@app_views.route("/auth/register", methods=["POST"])
def register():
    """Request a new user account (role "user").

    The account is created unapproved and the caller is NOT logged in:
    an admin has to approve it (see views/users.py) before it can sign
    in, using the reason given here to decide.
    """
    if register_limiter.is_limited(request.remote_addr):
        logger.warning(
            "Registration rate limit hit for %s", request.remote_addr)
        return jsonify({
            "error": "Too many accounts created recently. Try again later.",
        }), 429

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400, description="Not a JSON")
    try:
        only_allowed_fields(data, REGISTER_FIELDS)
        require_safe_name(data, "name")
        require_email(data)
        require_password(data)
        require_safe_text(
            data, "join_reason", max_length=MAX_JOIN_REASON_LENGTH)
        optional_enum(data, "lang", SUPPORTED_LANGS)
    except ValidationError as error:
        abort(400, description=error.message)

    register_limiter.record(request.remote_addr)
    email = data["email"].strip().lower()
    if _find_user_by_email(email) is not None:
        return jsonify(
            {"error": "An account with this email already exists"}), 409

    user = User(
        name=data["name"].strip(), email=email, role="user",
        email_verified=False, approved=False,
        join_reason=data["join_reason"].strip(),
        lang=normalize_lang(data.get("lang")))
    user.set_password(data["password"])
    user.save()
    return jsonify({"pending_approval": True}), 201


@app_views.route("/auth/login", methods=["POST"])
def login():
    """Log in with email + password, starting a session cookie."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400, description="Not a JSON")
    try:
        only_allowed_fields(data, LOGIN_FIELDS)
        require_non_empty_string(data, "email", max_length=254)
        require_non_empty_string(data, "password", max_length=128)
    except ValidationError as error:
        abort(400, description=error.message)

    email = data["email"].strip().lower()
    ip = request.remote_addr or "unknown"
    rate_key = "{}:{}".format(ip, email)
    if is_login_rate_limited(rate_key, ip=ip):
        logger.warning("Login rate limit hit for %s", rate_key)
        return jsonify({
            "error": "Too many failed login attempts. Try again later.",
        }), 429

    user = _find_user_by_email(email)
    if user is None:
        check_password_hash(_DUMMY_PASSWORD_HASH, data["password"])
        password_ok = False
    else:
        password_ok = user.check_password(data["password"])
    if not password_ok:
        record_login_failure(rate_key, ip=ip)
        logger.warning("Failed login attempt for %s", rate_key)
        # Same message either way — don't reveal whether the email is
        # registered at all.
        return jsonify({"error": "Invalid email or password"}), 401

    clear_login_failures(rate_key)
    if user.is_banned:
        return jsonify({
            "error": (
                "Your account has been banned for violating community rules"
            ),
            "banned": True,
        }), 403
    if not user.is_approved:
        # Only said after the password checked out, so this can't be
        # used to learn which emails have pending accounts.
        return jsonify({
            "error": "Your account is awaiting admin approval",
            "pending_approval": True,
        }), 403
    log_in(user)
    return jsonify(_serialize_user(user)), 200


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
    return jsonify(_serialize_user(user)), 200


def _delete_user_data(user):
    """Remove everything a user owns, in an order the database's foreign
    keys allow: their posts and replies (and anyone's replies to those),
    reports they filed or that were filed against their posts, their
    favorites, then the account itself."""
    own = [p for p in storage.all(ForumPost).values()
           if p.author_id == user.id]
    own_ids = {p.id for p in own}
    answers = [p for p in storage.all(ForumPost).values()
               if p.parent_id in own_ids and p.id not in own_ids]
    delete_forum_posts(own + answers)
    for report in [r for r in storage.all(PostReport).values()
                   if r.reporter_id == user.id]:
        report.delete()
    for favorite in [f for f in storage.all(Favorite).values()
                     if f.user_id == user.id]:
        favorite.delete()
    # Commit what references the user before the user row itself (see
    # delete_forum_posts for why the order isn't left to one flush).
    storage.save()
    user.delete()
    storage.save()


@app_views.route("/auth/account", methods=["DELETE"])
@login_required
def delete_account():
    """Permanently delete the logged-in user's own account and
    everything they posted or saved. Requires the account password (so a
    stolen session cookie alone can't wipe an account) and shares the
    login failure rate limit (so this can't be used to guess it).
    Admin accounts can't be deleted this way, so the site can't be left
    without one."""
    user = get_current_user()
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400, description="Not a JSON")
    try:
        only_allowed_fields(data, {"password"})
        require_non_empty_string(data, "password", max_length=128)
    except ValidationError as error:
        abort(400, description=error.message)
    if user.role == "admin":
        return jsonify({
            "error": "Admin accounts can't be deleted here",
        }), 403

    rate_key = "{}:{}".format(request.remote_addr, user.email)
    if is_login_rate_limited(rate_key):
        return jsonify({
            "error": "Too many failed attempts. Try again later.",
        }), 429
    if not user.check_password(data["password"]):
        record_login_failure(rate_key)
        return jsonify({"error": "Incorrect password"}), 401
    clear_login_failures(rate_key)

    _delete_user_data(user)
    session.clear()
    return jsonify({}), 200


@app_views.route("/auth/forgot-password", methods=["POST"])
def forgot_password():
    """Email a time-limited OTP for resetting a forgotten password.

    Always returns 200 regardless of whether the email is registered —
    otherwise this endpoint would double as an account-enumeration
    oracle (same reasoning as login's identical error either way).
    """
    if password_reset_request_limiter.is_limited(request.remote_addr):
        logger.warning(
            "Password-reset request rate limit hit for %s",
            request.remote_addr)
        return jsonify({
            "error": "Too many requests. Try again later.",
        }), 429

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400, description="Not a JSON")
    try:
        only_allowed_fields(data, FORGOT_PASSWORD_FIELDS)
        require_email(data)
        optional_enum(data, "lang", SUPPORTED_LANGS)
    except ValidationError as error:
        abort(400, description=error.message)

    password_reset_request_limiter.record(request.remote_addr)
    user = _find_user_by_email(data["email"])
    if user is not None and (not user.is_approved or user.is_banned):
        user = None
    if user is not None:
        otp = user.generate_password_reset_otp()
        user.save()
        _send_password_reset_email(user, otp, lang=data.get("lang"))
    return jsonify({}), 200


@app_views.route("/auth/reset-password", methods=["POST"])
def reset_password():
    """Set a new password using a valid, unexpired OTP from
    forgot-password, then log the caller in — they've just proven
    ownership of the account by way of the code, the same as a normal
    login proves it by way of the old password.
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400, description="Not a JSON")
    try:
        only_allowed_fields(data, RESET_PASSWORD_FIELDS)
        require_email(data)
        require_non_empty_string(data, "otp", max_length=6)
        require_password(data)
    except ValidationError as error:
        abort(400, description=error.message)

    email = data["email"].strip().lower()
    rate_key = "{}:{}".format(request.remote_addr, email)
    if password_reset_attempt_limiter.is_limited(rate_key):
        logger.warning(
            "Password-reset attempt rate limit hit for %s", rate_key)
        return jsonify({
            "error": "Too many attempts. Try again later.",
        }), 429

    user = _find_user_by_email(email)
    if (
        user is None
        or not user.is_approved
        or user.is_banned
        or not user.consume_password_reset_otp(data["otp"])
    ):
        password_reset_attempt_limiter.record(rate_key)
        logger.warning("Failed password-reset attempt for %s", rate_key)
        return jsonify({"error": "Invalid or expired code"}), 400

    password_reset_attempt_limiter.clear(rate_key)
    user.set_password(data["password"])
    # Sign every other device/cookie out: a reset usually means the old
    # password (and so possibly an old session) can't be trusted.
    user.session_epoch = (user.session_epoch or 0) + 1
    user.save()
    log_in(user)
    return jsonify(_serialize_user(user)), 200

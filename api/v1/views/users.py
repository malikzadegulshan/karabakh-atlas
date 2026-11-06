#!/usr/bin/python3
"""Admin-only views for reviewing new account requests.

Registering (see views/auth.py) creates an account with approved=False
that can't sign in. These endpoints are how an admin sees who is waiting
(and why they said they want to join), then approves or rejects them.
"""
from flask import jsonify, abort
from api.v1.views import app_views
from api.v1.auth_utils import admin_required
from api.v1.forum_utils import delete_forum_posts
from api.v1.mailer import build_welcome_email, send_email
from models import storage
from models.forum_post import ForumPost
from models.post_report import PostReport
from models.user import User


def _pending_user_or_404(user_id):
    """Return the still-pending user with this id, or 404.

    Approve/reject deliberately only ever act on accounts awaiting
    approval, so a stray or replayed request can never delete an
    existing member or an admin.
    """
    user = storage.all(User).get("User.{}".format(user_id))
    if user is None or user.is_approved or user.is_banned:
        abort(404, description="Pending user not found")
    return user


def _approved_user_or_404(user_id):
    """Return an approved user with this id, or 404."""
    user = storage.all(User).get("User.{}".format(user_id))
    if user is None or not user.is_approved:
        abort(404, description="User not found")
    return user


def _pending_dict(user):
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "join_reason": user.join_reason,
        "created_at": user.created_at.isoformat(),
    }


def _member_dict(user):
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "banned": user.is_banned,
        "created_at": user.created_at.isoformat(),
    }


def _purge_user_content(user):
    """Remove all forum posts, replies, and reports filed by `user`."""
    own = [
        p for p in storage.all(ForumPost).values() if p.author_id == user.id
    ]
    own_ids = {p.id for p in own}
    answers = [
        p for p in storage.all(ForumPost).values()
        if p.parent_id in own_ids and p.id not in own_ids
    ]
    delete_forum_posts(own + answers)
    storage.save()
    for report in [
        r for r in storage.all(PostReport).values()
        if r.reporter_id == user.id
    ]:
        report.delete()
    storage.save()


@app_views.route("/users", methods=["GET"])
@admin_required
def list_approved_users():
    """List approved non-admin members (including banned accounts)."""
    members = [
        u for u in storage.all(User).values()
        if u.is_approved and u.role != "admin"
    ]
    members.sort(key=lambda u: u.created_at, reverse=True)
    return jsonify([_member_dict(u) for u in members]), 200


@app_views.route("/users/pending", methods=["GET"])
@admin_required
def list_pending_users():
    """List accounts awaiting approval, oldest request first."""
    pending = [u for u in storage.all(User).values() if not u.is_approved]
    pending.sort(key=lambda u: u.created_at)
    return jsonify([_pending_dict(u) for u in pending]), 200


def _send_account_approved_email(user):
    lang = getattr(user, "lang", None)
    subject, text_body, html_body = build_welcome_email(user.name, lang=lang)
    send_email(user.email, subject, text_body, html_body=html_body)


@app_views.route("/users/<user_id>/approve", methods=["POST"])
@admin_required
def approve_user(user_id):
    """Approve a pending account so its owner can sign in."""
    user = _pending_user_or_404(user_id)
    user.approved = True
    user.save()
    _send_account_approved_email(user)
    return jsonify({}), 200


@app_views.route("/users/<user_id>/reject", methods=["DELETE"])
@admin_required
def reject_user(user_id):
    """Reject a pending account by deleting it (a pending account has
    no posts or favorites, so there's nothing else to clean up). The
    person can register again with the same email."""
    user = _pending_user_or_404(user_id)
    user.delete()
    storage.save()
    return jsonify({}), 200


@app_views.route("/users/<user_id>/ban", methods=["POST"])
@admin_required
def ban_user(user_id):
    """Ban an approved non-admin user and purge their forum content."""
    user = _approved_user_or_404(user_id)
    if user.role == "admin":
        return jsonify({"error": "Admin accounts cannot be banned"}), 403
    _purge_user_content(user)
    user.banned = True
    user.password_reset_otp = None
    user.password_reset_otp_expires_at = None
    user.session_epoch = (user.session_epoch or 0) + 1
    user.save()
    return jsonify(_member_dict(user)), 200


@app_views.route("/users/<user_id>/unban", methods=["POST"])
@admin_required
def unban_user(user_id):
    """Restore a banned user account so they can sign in again."""
    user = _approved_user_or_404(user_id)
    if not user.is_banned:
        abort(404, description="Banned user not found")
    user.banned = False
    user.save()
    return jsonify(_member_dict(user)), 200

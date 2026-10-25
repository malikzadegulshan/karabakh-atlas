#!/usr/bin/python3
"""Admin-only views for reviewing new account requests.

Registering (see views/auth.py) creates an account with approved=False
that can't sign in. These endpoints are how an admin sees who is waiting
(and why they said they want to join), then approves or rejects them.
"""
from flask import jsonify, abort
from api.v1.views import app_views
from api.v1.auth_utils import admin_required
from models import storage
from models.user import User


def _pending_user_or_404(user_id):
    """Return the still-pending user with this id, or 404.

    Approve/reject deliberately only ever act on accounts awaiting
    approval, so a stray or replayed request can never delete an
    existing member or an admin.
    """
    user = storage.all(User).get("User.{}".format(user_id))
    if user is None or user.is_approved:
        abort(404, description="Pending user not found")
    return user


def _pending_dict(user):
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "join_reason": user.join_reason,
        "created_at": user.created_at.isoformat(),
    }


@app_views.route("/users/pending", methods=["GET"])
@admin_required
def list_pending_users():
    """List accounts awaiting approval, oldest request first."""
    pending = [u for u in storage.all(User).values() if not u.is_approved]
    pending.sort(key=lambda u: u.created_at)
    return jsonify([_pending_dict(u) for u in pending]), 200


@app_views.route("/users/<user_id>/approve", methods=["POST"])
@admin_required
def approve_user(user_id):
    """Approve a pending account so its owner can sign in."""
    user = _pending_user_or_404(user_id)
    user.approved = True
    user.save()
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

#!/usr/bin/python3
"""RESTful API views for the community forum: users submit opinions
about Karabakh, a city, or a point of interest; nothing is publicly
visible until an admin approves it.

Security notes (this endpoint accepts free-text from any logged-in
visitor, so it's worth being explicit about what protects what):
  - Every write requires a session (login_required); moderation and
    deletion of someone else's post additionally require the admin
    role. The author is always taken from the session, never from the
    request body, so a post can't be submitted "as" another user.
  - `status` is never client-settable on create — every new post starts
    "pending" server-side, regardless of what the request body says
    (only_allowed_fields rejects a "status" key outright).
  - `body` is stored as plain text and is never interpreted as HTML by
    this API; the frontend is responsible for escaping it on render
    (same convention already used for city descriptions). This file
    does no HTML sanitization of its own because it does no HTML
    rendering of its own.
  - Creation is rate-limited per account (see forum_post_limiter) so a
    single compromised or scripted account can't flood the moderation
    queue.
  - Reads default to "approved" only; only an admin can request the
    pending/rejected queues, and only for their own moderation view —
    unapproved content never reaches an anonymous or non-admin caller.
"""
import logging
from datetime import datetime
from flask import jsonify, abort, request
from api.v1.views import app_views
from api.v1.auth_utils import (
    get_current_user, login_required, admin_required, forum_post_limiter,
)
from api.v1.validation import (
    ValidationError,
    require_non_empty_string,
    only_allowed_fields,
    optional_enum,
)
from api.v1.contributions import approved_post_count, contribution_tier
from models import storage
from models.city import City
from models.user import User
from models.forum_post import (
    ForumPost, STATUSES, TOPICS, DEFAULT_TOPIC,
)
from models.news_item import NewsItem

FORUM_BODY_MAX_LENGTH = 2000
CREATE_FIELDS = {"body", "target_city_id", "target_news_id", "topic"}
MODERATE_FIELDS = {"status"}
MODERATABLE_STATUSES = {"approved", "rejected"}

logger = logging.getLogger(__name__)


def _user_name(user_id):
    user = storage.all(User).get("User.{}".format(user_id))
    return user.name if user else None


def _city_name(city_id):
    city = storage.all(City).get("City.{}".format(city_id))
    return city.name if city else None


def _is_general(post):
    return post.target_city_id is None and post.target_news_id is None


def _topic_of(post):
    """A general post's topic (older ones read as "general"); None for
    place- and news-scoped posts, which have no topic."""
    if not _is_general(post):
        return None
    return post.topic or DEFAULT_TOPIC


def _news_title(news_id):
    item = storage.all(NewsItem).get("NewsItem.{}".format(news_id))
    return item.title if item else None


def _serialize(post):
    data = post.to_dict()
    data["author_name"] = _user_name(post.author_id)
    data["author_tier"] = contribution_tier(
        approved_post_count(post.author_id))
    data["target_city_name"] = (
        _city_name(post.target_city_id) if post.target_city_id else None)
    data["topic"] = _topic_of(post)
    data["target_news_title"] = (
        _news_title(post.target_news_id) if post.target_news_id else None)
    return data


def _sorted_newest_first(posts):
    return sorted(posts, key=lambda p: p.created_at, reverse=True)


@app_views.route("/forum/posts", methods=["POST"])
@login_required
def create_forum_post():
    """Submit a new opinion. Starts out "pending" — never visible to
    anyone but its author and admins until a moderator approves it —
    except for admins themselves, who are implicitly trusted moderators
    and so are auto-approved and exempt from the rate limit below;
    everyone else still goes through the queue."""
    user = get_current_user()
    is_admin = user.role == "admin"
    if not is_admin and forum_post_limiter.is_limited(user.id):
        logger.warning("Forum post rate limit hit for user %s", user.id)
        return jsonify({
            "error": "Too many posts submitted recently. Try again later.",
        }), 429

    data = request.get_json(silent=True)
    if data is None:
        abort(400, description="Not a JSON")
    try:
        only_allowed_fields(data, CREATE_FIELDS)
        require_non_empty_string(
            data, "body", max_length=FORUM_BODY_MAX_LENGTH)
        optional_enum(data, "topic", set(TOPICS))
    except ValidationError as error:
        abort(400, description=error.message)

    target_city_id = data.get("target_city_id")
    if target_city_id is not None:
        if not isinstance(target_city_id, str):
            abort(400, description="target_city_id must be a string")
        if storage.all(City).get("City.{}".format(target_city_id)) is None:
            abort(400, description="target_city_id does not exist")

    target_news_id = data.get("target_news_id")
    if target_news_id is not None:
        if target_city_id is not None:
            abort(400, description=(
                "A post can target a city or a news item, not both"))
        if not isinstance(target_news_id, str):
            abort(400, description="target_news_id must be a string")
        if storage.all(NewsItem).get(
                "NewsItem.{}".format(target_news_id)) is None:
            abort(400, description="target_news_id does not exist")

    topic = data.get("topic")
    is_general = target_city_id is None and target_news_id is None
    if topic is not None and not is_general:
        abort(400, description=(
            "topic only applies to general posts, not place or news posts"))

    if not is_admin:
        forum_post_limiter.record(user.id)
    post = ForumPost(
        author_id=user.id,
        target_city_id=target_city_id,
        target_news_id=target_news_id,
        topic=(topic or DEFAULT_TOPIC) if is_general else None,
        body=data["body"].strip(),
        status="approved" if is_admin else "pending",
    )
    if is_admin:
        post.moderated_by = user.id
        post.moderated_at = datetime.utcnow()
    post.save()
    return jsonify(_serialize(post)), 201


@app_views.route("/forum/posts", methods=["GET"])
def list_forum_posts():
    """List forum posts.

    Query params:
      - city_id: only posts about this city/POI.
      - news_id: only comments on this news item.
      - topic: only general posts in this topic (see TOPICS in
        models/forum_post.py); older posts without one count as
        "general". Place- and news-scoped posts have no topic, so any
        topic filter excludes them.
        (Omit both for general Karabakh-wide opinions — neither a city
        nor a news item targeted.) The one exception is an admin
        passing status= with neither: that's the moderation queue, and
        it spans every target (general, place, and news comments) so
        nothing pending is invisible to moderation.
      - mine=true: only the logged-in caller's own posts, any status —
        so someone can see whether their own submission is still
        pending or was rejected. Requires login; overrides `status`.
      - status: pending/approved/rejected — admin-only moderation
        queue. Ignored (silently falls back to "approved") for anyone
        who isn't an admin, so unapproved content never leaks to a
        request that merely guesses the query param.
    """
    user = get_current_user()
    city_id = request.args.get("city_id")
    news_id = request.args.get("news_id")
    topic = request.args.get("topic")
    if topic is not None and topic not in TOPICS:
        abort(400, description="Invalid topic filter")
    mine = request.args.get("mine") == "true"
    status_param = request.args.get("status")

    posts = list(storage.all(ForumPost).values())
    is_moderation_queue = (
        user is not None and user.role == "admin" and bool(status_param)
        and not mine)
    if news_id:
        posts = [p for p in posts if p.target_news_id == news_id]
    elif city_id:
        posts = [p for p in posts if p.target_city_id == city_id]
    elif not is_moderation_queue:
        posts = [
            p for p in posts
            if p.target_city_id is None and p.target_news_id is None]

    if mine:
        if user is None:
            return jsonify({"error": "Login required"}), 401
        posts = [p for p in posts if p.author_id == user.id]
    elif user is not None and user.role == "admin" and status_param:
        if status_param not in STATUSES:
            abort(400, description="Invalid status filter")
        posts = [p for p in posts if p.status == status_param]
    else:
        posts = [p for p in posts if p.status == "approved"]

    if topic is not None:
        posts = [p for p in posts if _topic_of(p) == topic]

    return jsonify([_serialize(p) for p in _sorted_newest_first(posts)])


@app_views.route("/forum/posts/<post_id>/status", methods=["PUT"])
@admin_required
def moderate_forum_post(post_id):
    """Approve or reject a pending (or previously moderated) post."""
    post = storage.all(ForumPost).get("ForumPost.{}".format(post_id))
    if post is None:
        abort(404)
    data = request.get_json(silent=True)
    if data is None:
        abort(400, description="Not a JSON")
    try:
        only_allowed_fields(data, MODERATE_FIELDS)
        optional_enum(data, "status", MODERATABLE_STATUSES)
    except ValidationError as error:
        abort(400, description=error.message)
    if "status" not in data:
        abort(400, description="status is required")

    admin = get_current_user()
    post.status = data["status"]
    post.moderated_by = admin.id
    post.moderated_at = datetime.utcnow()
    post.save()
    return jsonify(_serialize(post)), 200


@app_views.route("/forum/posts/<post_id>", methods=["DELETE"])
@login_required
def delete_forum_post(post_id):
    """Delete a post — its own author, or any admin, may do this."""
    post = storage.all(ForumPost).get("ForumPost.{}".format(post_id))
    if post is None:
        abort(404)
    user = get_current_user()
    if user.id != post.author_id and user.role != "admin":
        return jsonify({"error": "Not allowed to delete this post"}), 403
    post.delete()
    storage.save()
    return jsonify({}), 200

#!/usr/bin/python3
"""RESTful API views for NewsItem objects: news posts shown in the
frontend's News tab.

Reads are public (same as regions/cities); writes require an admin
session, enforced by require_admin_for_writes in api/v1/app.py (see
ADMIN_GATED_PREFIXES there) rather than a per-route decorator — same
pattern already used for regions/cities/historical events, so nobody
but an admin can ever add, edit, or delete news.
"""
from flask import jsonify, abort, request
from api.v1.views import app_views
from models import storage
from models.forum_post import ForumPost
from models.news_item import NewsItem
from api.v1.validation import (
    ValidationError,
    require_non_empty_string,
    optional_url,
    optional_i18n_dict,
    only_allowed_fields,
)

NEWS_FIELDS = {
    "title", "body", "image_url", "source_url", "title_i18n", "body_i18n",
}


def _validate_news_data(data, *, require_required_fields):
    """Validate a NewsItem request body; raises ValidationError on
    failure."""
    only_allowed_fields(data, NEWS_FIELDS)
    if require_required_fields or "title" in data:
        require_non_empty_string(data, "title", max_length=200)
    if require_required_fields or "body" in data:
        require_non_empty_string(data, "body", max_length=5000)
    optional_url(data, "image_url", max_length=500)
    optional_url(data, "source_url", max_length=500)
    optional_i18n_dict(data, "title_i18n")
    optional_i18n_dict(data, "body_i18n")


def _serialize(item):
    data = item.to_dict()
    # Approved comments only — the same "visible to everyone" count a
    # reader would see in the list, never one that leaks pending posts.
    data["comment_count"] = sum(
        1 for post in storage.all(ForumPost).values()
        if post.target_news_id == item.id and post.status == "approved")
    return data


def _newest_first(items):
    return sorted(items, key=lambda n: n.created_at, reverse=True)


@app_views.route("/news", methods=["GET"])
def get_news():
    """Return all NewsItem objects, newest first."""
    items = list(storage.all(NewsItem).values())
    return jsonify([_serialize(n) for n in _newest_first(items)])


@app_views.route("/news", methods=["POST"])
def create_news_item():
    """Create a new NewsItem object."""
    data = request.get_json(silent=True)
    if data is None:
        abort(400, description="Not a JSON")
    try:
        _validate_news_data(data, require_required_fields=True)
    except ValidationError as error:
        abort(400, description=error.message)
    item = NewsItem(**data)
    item.save()
    return jsonify(_serialize(item)), 201


@app_views.route("/news/<news_id>", methods=["PUT"])
def update_news_item(news_id):
    """Update an existing NewsItem object from a JSON body."""
    item = storage.all(NewsItem).get("NewsItem.{}".format(news_id))
    if item is None:
        abort(404)
    data = request.get_json(silent=True)
    if data is None:
        abort(400, description="Not a JSON")
    try:
        _validate_news_data(data, require_required_fields=False)
    except ValidationError as error:
        abort(400, description=error.message)
    for key, value in data.items():
        setattr(item, key, value)
    item.save()
    return jsonify(_serialize(item)), 200


@app_views.route("/news/<news_id>", methods=["DELETE"])
def delete_news_item(news_id):
    """Delete a NewsItem and its comments, or 404 if not found."""
    item = storage.all(NewsItem).get("NewsItem.{}".format(news_id))
    if item is None:
        abort(404)
    # Comments reference the item by foreign key, so they have to go
    # first (Postgres would reject deleting a still-referenced row).
    for post in list(storage.all(ForumPost).values()):
        if post.target_news_id == item.id:
            post.delete()
    item.delete()
    storage.save()
    return jsonify({}), 200

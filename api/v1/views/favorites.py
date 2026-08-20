#!/usr/bin/python3
"""RESTful API views for a logged-in user's saved places (favorites).

Every route requires a session (login_required) — favorites are always
scoped to the caller, never client-settable to another user's id, the
same convention forum.py uses for post authorship.
"""
from flask import jsonify, abort, request
from api.v1.views import app_views
from api.v1.auth_utils import get_current_user, login_required
from api.v1.validation import ValidationError, only_allowed_fields
from models import storage
from models.city import City
from models.favorite import Favorite

CREATE_FIELDS = {"city_id"}


def _find_favorite(user_id, city_id):
    for favorite in storage.all(Favorite).values():
        if favorite.user_id == user_id and favorite.city_id == city_id:
            return favorite
    return None


@app_views.route("/favorites", methods=["GET"])
@login_required
def list_favorites():
    """List the places the logged-in caller has saved, newest first."""
    user = get_current_user()
    favorites = [
        f for f in storage.all(Favorite).values() if f.user_id == user.id
    ]
    favorites.sort(key=lambda f: f.created_at, reverse=True)
    cities = []
    for favorite in favorites:
        city = storage.all(City).get("City.{}".format(favorite.city_id))
        if city is not None:
            cities.append(city.to_dict())
    return jsonify(cities)


@app_views.route("/favorites", methods=["POST"])
@login_required
def add_favorite():
    """Save a place. Idempotent — favoriting an already-saved place just
    returns the existing bookmark instead of erroring, so a client can't
    get a toggle button out of sync with a double-click or a retry."""
    user = get_current_user()
    data = request.get_json(silent=True)
    if data is None:
        abort(400, description="Not a JSON")
    try:
        only_allowed_fields(data, CREATE_FIELDS)
    except ValidationError as error:
        abort(400, description=error.message)

    city_id = data.get("city_id")
    if not isinstance(city_id, str) or not city_id:
        abort(400, description="city_id is required")
    if storage.all(City).get("City.{}".format(city_id)) is None:
        abort(400, description="city_id does not exist")

    existing = _find_favorite(user.id, city_id)
    if existing is not None:
        return jsonify(existing.to_dict()), 200

    favorite = Favorite(user_id=user.id, city_id=city_id)
    favorite.save()
    return jsonify(favorite.to_dict()), 201


@app_views.route("/favorites/<city_id>", methods=["DELETE"])
@login_required
def remove_favorite(city_id):
    """Un-save a place. Idempotent — removing something that was never
    (or is no longer) saved is a no-op 200, not a 404, for the same
    toggle-button reason as add_favorite()'s idempotence above."""
    user = get_current_user()
    favorite = _find_favorite(user.id, city_id)
    if favorite is not None:
        favorite.delete()
        storage.save()
    return jsonify({}), 200

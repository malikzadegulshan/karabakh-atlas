#!/usr/bin/python3
"""RESTful API views for City objects."""
import math
import re
from api.v1.views import app_views
from flask import jsonify, abort, request
from models import storage
from models.region import Region
from models.city import City
from models.forum_post import ForumPost
from api.v1.forum_utils import delete_forum_posts
from models.favorite import Favorite
from models.image import Image
from api.v1.validation import (
    ValidationError,
    require_non_empty_string,
    require_number_in_range,
    optional_string,
    optional_url,
    optional_i18n_dict,
    optional_enum,
    only_allowed_fields,
)

# Matches the URL POST /images (api/v1/views/images.py) hands back, so
# an old photo can be told apart from a pasted external link — deleting
# or replacing one of *our* uploads should also drop the underlying
# Image row; a link to somewhere else isn't ours to delete.
_UPLOADED_IMAGE_ID_RE = re.compile(r"/api/v1/images/([^/?#]+)/?$")


def _delete_uploaded_image_if_ours(url):
    """Delete the Image row url points at, if it's one of our own
    uploads (no-op for an external link, a blank field, or an id that's
    already gone)."""
    if not url:
        return
    match = _UPLOADED_IMAGE_ID_RE.search(url)
    if not match:
        return
    image = storage.all(Image).get("Image.{}".format(match.group(1)))
    if image is not None:
        image.delete()


# "city" renders as a persistent map label; every other value is a
# user-added point of interest, rendered as a small marker only when
# zoomed in. Keep in sync with CITY_CATEGORIES in frontend/admin.js.
CITY_CATEGORIES = {
    "city", "road", "cafe", "restaurant", "hotel", "landmark", "museum",
    "park", "university", "school", "hospital", "pharmacy", "bank",
    "government", "police", "fire_station", "mosque", "church",
    "fuel_station", "parking", "shop", "grocery_store", "other",
}

CITY_FIELDS = {
    "name", "latitude", "longitude", "description", "alt_names",
    "image_url", "image_credit", "image_url_before", "image_before_credit",
    "phone", "website", "name_i18n", "description_i18n", "category",
}


def _validate_city_data(data, *, require_required_fields):
    """Validate a City request body; raises ValidationError on failure."""
    only_allowed_fields(data, CITY_FIELDS)
    if require_required_fields or "name" in data:
        require_non_empty_string(data, "name")
    if require_required_fields or "latitude" in data:
        require_number_in_range(data, "latitude", -90, 90)
    if require_required_fields or "longitude" in data:
        require_number_in_range(data, "longitude", -180, 180)
    optional_string(data, "description")
    optional_string(data, "alt_names", max_length=255)
    optional_url(data, "image_url", max_length=500)
    optional_string(data, "image_credit", max_length=255)
    optional_url(data, "image_url_before", max_length=500)
    optional_string(data, "image_before_credit", max_length=255)
    optional_string(data, "phone", max_length=30)
    optional_url(data, "website", max_length=500)
    optional_i18n_dict(data, "name_i18n")
    optional_i18n_dict(data, "description_i18n")
    # Unlike the optional_string/optional_url fields above, category
    # isn't something a client can legitimately clear — every City has
    # one — so an explicit null is rejected outright here rather than
    # falling through to optional_enum(), which treats None as "field
    # omitted" and would let it slip past validation only for the
    # unconditional setattr loop in update_city() below to actually set
    # city.category = None on the object.
    if "category" in data and data["category"] is None:
        raise ValidationError("category cannot be null")
    optional_enum(data, "category", CITY_CATEGORIES)


@app_views.route("/regions/<region_id>/cities", methods=["GET"])
def get_cities_by_region(region_id):
    """Return all City objects that belong to a given Region."""
    region = storage.all(Region).get("Region.{}".format(region_id))
    if region is None:
        abort(404)
    cities = [c for c in storage.all(City).values()
              if c.region_id == region_id]
    return jsonify([c.to_dict() for c in cities])


@app_views.route("/regions/<region_id>/cities", methods=["POST"])
def create_city(region_id):
    """Create a new City object under a given Region."""
    region = storage.all(Region).get("Region.{}".format(region_id))
    if region is None:
        abort(404)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400, description="Not a JSON")
    try:
        _validate_city_data(data, require_required_fields=True)
    except ValidationError as error:
        abort(400, description=error.message)
    data["region_id"] = region_id
    data.setdefault("category", "city")
    city = City(**data)
    city.save()
    return jsonify(city.to_dict()), 201


# Bulk import (POST /regions/<id>/cities/import) -----------------------

IMPORT_MAX_ROWS = 300
# Two non-city places with the same name count as the same place only if
# they're this close (a "Pharmacy" in two different towns is two places).
IMPORT_DUPLICATE_RADIUS_KM = 0.5


def _normalized_name(value):
    return " ".join(str(value).lower().split())


def _all_names(name, name_i18n):
    """Every name a place goes by — the main one and each translation —
    normalized, so "Xankəndi" matches an existing "Khankendi" whose az
    translation is "Xankəndi"."""
    names = {_normalized_name(name)}
    if isinstance(name_i18n, dict):
        names.update(_normalized_name(v) for v in name_i18n.values() if v)
    return names


def _distance_km(lat1, lng1, lat2, lng2):
    """Great-circle distance between two points, in kilometres."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((phi2 - phi1) / 2) ** 2
         + math.cos(phi1) * math.cos(phi2)
         * math.sin(math.radians(lng2 - lng1) / 2) ** 2)
    return 6371 * 2 * math.asin(math.sqrt(a))


def _is_same_place(candidate, existing):
    """True if `candidate` (a dict) is already covered by `existing`
    (a dict-like place): they share a name, and either is a plain city
    (cities are matched by name alone) or they're within
    IMPORT_DUPLICATE_RADIUS_KM of each other."""
    if not (_all_names(candidate["name"], candidate.get("name_i18n"))
            & _all_names(existing["name"], existing.get("name_i18n"))):
        return False
    if candidate.get("category", "city") == "city" \
            or existing.get("category") == "city":
        return True
    return _distance_km(
        candidate["latitude"], candidate["longitude"],
        existing["latitude"], existing["longitude"],
    ) <= IMPORT_DUPLICATE_RADIUS_KM


@app_views.route("/regions/<region_id>/cities/import", methods=["POST"])
def import_cities(region_id):
    """Bulk-add places from parsed spreadsheet rows (admin only, via the
    /regions prefix gate in api/v1/app.py).

    Body: {"rows": [<place fields>, ...], "dry_run": true|false}. Every
    row is validated with exactly the rules POST /regions/<id>/cities
    applies, so an import can never store anything a hand-added place
    couldn't. A row is "new", a "duplicate" (a place with the same name
    already exists in the region, or earlier in this same file — see
    _is_same_place) or an "error"; only new rows are saved, and only when
    dry_run is false, so the same request doubles as the preview and
    re-importing a corrected file is safe.
    """
    region = storage.all(Region).get("Region.{}".format(region_id))
    if region is None:
        abort(404)
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        abort(400, description="Not a JSON")
    rows = body.get("rows")
    dry_run = body.get("dry_run", True)
    if not isinstance(rows, list) or not rows:
        abort(400, description="rows must be a non-empty list")
    if len(rows) > IMPORT_MAX_ROWS:
        abort(400, description=(
            "At most {} rows per import".format(IMPORT_MAX_ROWS)))
    if not isinstance(dry_run, bool):
        abort(400, description="dry_run must be true or false")

    known = [c.to_dict() for c in storage.all(City).values()
             if c.region_id == region_id]
    results = []
    to_create = []
    for index, row in enumerate(rows):
        result = {"row": index, "name": None, "status": "error"}
        results.append(result)
        if not isinstance(row, dict):
            result["error"] = "Row is not an object"
            continue
        result["name"] = row.get("name") if isinstance(
            row.get("name"), str) else None
        try:
            _validate_city_data(row, require_required_fields=True)
        except ValidationError as error:
            result["error"] = error.message
            continue
        place = dict(row)
        place.setdefault("category", "city")
        match = next((k for k in known if _is_same_place(place, k)), None)
        if match is not None:
            result["status"] = "duplicate"
            result["duplicate_of"] = match["name"]
            continue
        result["status"] = "new"
        known.append(place)
        to_create.append(place)

    if not dry_run:
        for place in to_create:
            place["region_id"] = region_id
            storage.new(City(**place))
        if to_create:
            storage.save()
    return jsonify({
        "dry_run": dry_run,
        "created": 0 if dry_run else len(to_create),
        "results": results,
    })


@app_views.route("/cities", methods=["GET"])
def get_cities():
    """Return all City objects, optionally filtered by name via ?q=."""
    search = request.args.get("q")
    cities = list(storage.all(City).values())
    if search:
        cities = [c for c in cities if search.lower() in c.name.lower()]
    return jsonify([c.to_dict() for c in cities])


@app_views.route("/cities/<city_id>", methods=["GET"])
def get_city(city_id):
    """Return a single City object by id, or 404 if not found."""
    city = storage.all(City).get("City.{}".format(city_id))
    if city is None:
        abort(404)
    return jsonify(city.to_dict())


@app_views.route("/cities/<city_id>", methods=["DELETE"])
def delete_city(city_id):
    """Delete a City object by id (and any forum posts or favorites
    referencing it), or 404 if not found."""
    city = storage.all(City).get("City.{}".format(city_id))
    if city is None:
        abort(404)
    delete_forum_posts([p for p in storage.all(ForumPost).values()
                        if p.target_city_id == city_id])
    for favorite in [f for f in storage.all(Favorite).values()
                     if f.city_id == city_id]:
        favorite.delete()
    _delete_uploaded_image_if_ours(city.image_url)
    _delete_uploaded_image_if_ours(city.image_url_before)
    city.delete()
    storage.save()
    return jsonify({}), 200


@app_views.route("/cities/<city_id>", methods=["PUT"])
def update_city(city_id):
    """Update an existing City object from a JSON body."""
    city = storage.all(City).get("City.{}".format(city_id))
    if city is None:
        abort(404)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400, description="Not a JSON")
    try:
        _validate_city_data(data, require_required_fields=False)
    except ValidationError as error:
        abort(400, description=error.message)
    image_url_fields = ("image_url", "image_url_before")
    for key, value in data.items():
        if key in image_url_fields and value != getattr(city, key):
            _delete_uploaded_image_if_ours(getattr(city, key))
        setattr(city, key, value)
    city.save()
    return jsonify(city.to_dict()), 200

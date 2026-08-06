#!/usr/bin/python3
"""RESTful API views for City objects."""
from api.v1.views import app_views
from flask import jsonify, abort, request
from models import storage
from models.region import Region
from models.city import City
from api.v1.validation import (
    ValidationError,
    require_non_empty_string,
    require_number_in_range,
    optional_string,
    optional_i18n_dict,
    only_allowed_fields,
)

CITY_FIELDS = {
    "name", "latitude", "longitude", "description", "alt_names",
    "image_url", "image_credit", "name_i18n", "description_i18n",
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
    optional_string(data, "image_url", max_length=500)
    optional_string(data, "image_credit", max_length=255)
    optional_i18n_dict(data, "name_i18n")
    optional_i18n_dict(data, "description_i18n")


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
    if data is None:
        abort(400, description="Not a JSON")
    try:
        _validate_city_data(data, require_required_fields=True)
    except ValidationError as error:
        abort(400, description=error.message)
    data["region_id"] = region_id
    city = City(**data)
    city.save()
    return jsonify(city.to_dict()), 201


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
    """Delete a City object by id, or 404 if not found."""
    city = storage.all(City).get("City.{}".format(city_id))
    if city is None:
        abort(404)
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
    if data is None:
        abort(400, description="Not a JSON")
    try:
        _validate_city_data(data, require_required_fields=False)
    except ValidationError as error:
        abort(400, description=error.message)
    for key, value in data.items():
        setattr(city, key, value)
    city.save()
    return jsonify(city.to_dict()), 200

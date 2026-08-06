#!/usr/bin/python3
"""RESTful API views for Region objects."""
from api.v1.views import app_views
from flask import jsonify, abort, request
from models import storage
from models.region import Region
from models.city import City
from api.v1.validation import (
    ValidationError,
    require_non_empty_string,
    optional_string,
    only_allowed_fields,
)

REGION_FIELDS = {"name", "description"}


@app_views.route("/regions", methods=["GET"])
def get_regions():
    """Return the list of all Region objects."""
    return jsonify([r.to_dict() for r in storage.all(Region).values()])


@app_views.route("/regions/<region_id>", methods=["GET"])
def get_region(region_id):
    """Return a single Region object by id, or 404 if not found."""
    region = storage.all(Region).get("Region.{}".format(region_id))
    if region is None:
        abort(404)
    return jsonify(region.to_dict())


@app_views.route("/regions/<region_id>", methods=["DELETE"])
def delete_region(region_id):
    """Delete a Region object, and its cities, by id, or 404 if not found."""
    region = storage.all(Region).get("Region.{}".format(region_id))
    if region is None:
        abort(404)
    for city in [c for c in storage.all(City).values()
                 if c.region_id == region_id]:
        city.delete()
    region.delete()
    storage.save()
    return jsonify({}), 200


@app_views.route("/regions", methods=["POST"])
def create_region():
    """Create a new Region object from a JSON body."""
    data = request.get_json(silent=True)
    if data is None:
        abort(400, description="Not a JSON")
    try:
        only_allowed_fields(data, REGION_FIELDS)
        require_non_empty_string(data, "name")
        optional_string(data, "description")
    except ValidationError as error:
        abort(400, description=error.message)
    region = Region(**data)
    region.save()
    return jsonify(region.to_dict()), 201


@app_views.route("/regions/<region_id>", methods=["PUT"])
def update_region(region_id):
    """Update an existing Region object from a JSON body."""
    region = storage.all(Region).get("Region.{}".format(region_id))
    if region is None:
        abort(404)
    data = request.get_json(silent=True)
    if data is None:
        abort(400, description="Not a JSON")
    try:
        only_allowed_fields(data, REGION_FIELDS)
        if "name" in data:
            require_non_empty_string(data, "name")
        optional_string(data, "description")
    except ValidationError as error:
        abort(400, description=error.message)
    for key, value in data.items():
        setattr(region, key, value)
    region.save()
    return jsonify(region.to_dict()), 200

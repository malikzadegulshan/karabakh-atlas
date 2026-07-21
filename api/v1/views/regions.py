#!/usr/bin/python3
"""RESTful API views for Region objects."""
from api.v1.views import app_views
from flask import jsonify, abort, request
from models import storage
from models.region import Region


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
    """Delete a Region object by id, or 404 if not found."""
    region = storage.all(Region).get("Region.{}".format(region_id))
    if region is None:
        abort(404)
    region.delete()
    storage.save()
    return jsonify({}), 200


@app_views.route("/regions", methods=["POST"])
def create_region():
    """Create a new Region object from a JSON body."""
    data = request.get_json(silent=True)
    if data is None:
        abort(400, description="Not a JSON")
    if "name" not in data:
        abort(400, description="Missing name")
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
    for key, value in data.items():
        if key not in ("id", "created_at", "updated_at"):
            setattr(region, key, value)
    region.save()
    return jsonify(region.to_dict()), 200

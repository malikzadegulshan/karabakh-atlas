#!/usr/bin/python3
"""RESTful API views for City objects."""
from api.v1.views import app_views
from flask import jsonify, abort, request
from models import storage
from models.region import Region
from models.city import City


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
    for field in ("name", "latitude", "longitude"):
        if field not in data:
            abort(400, description="Missing {}".format(field))
    data = {k: v for k, v in data.items()
            if k not in ("id", "created_at", "updated_at", "region_id")}
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
    for key, value in data.items():
        if key not in ("id", "created_at", "updated_at", "region_id"):
            setattr(city, key, value)
    city.save()
    return jsonify(city.to_dict()), 200

#!/usr/bin/python3
"""Index view: status and stats endpoints for the API."""
from api.v1.views import app_views
from flask import jsonify
from models import storage
from models.region import Region
from models.city import City


@app_views.route("/status", methods=["GET"])
def status():
    """Return a simple OK status payload."""
    return jsonify({"status": "OK"})


@app_views.route("/stats", methods=["GET"])
def stats():
    """Return the count of each object type currently in storage."""
    return jsonify({
        "regions": len(storage.all(Region)),
        "cities": len(storage.all(City)),
    })

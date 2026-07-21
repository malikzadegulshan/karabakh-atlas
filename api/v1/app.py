#!/usr/bin/python3
"""Starts the Flask API application for the Karabakh Atlas backend."""
import os
from flask import Flask, jsonify
from flask_cors import CORS
from models import storage
from api.v1.views import app_views

app = Flask(__name__)
app.url_map.strict_slashes = False
app.register_blueprint(app_views)
CORS(app, resources={r"/api/v1/*": {"origins": "*"}})


@app.teardown_appcontext
def teardown_storage(exception):
    """Close the storage session at the end of each request."""
    storage.close()


@app.errorhandler(400)
def bad_request(error):
    """Return a JSON 400 response instead of Flask's default HTML page."""
    message = getattr(error, "description", "Bad request")
    return jsonify({"error": message}), 400


@app.errorhandler(404)
def not_found(error):
    """Return a JSON 404 response instead of Flask's default HTML page."""
    return jsonify({"error": "Not found"}), 404


if __name__ == "__main__":
    host = os.environ.get("KBA_API_HOST", "0.0.0.0")
    port = int(os.environ.get("KBA_API_PORT", "5000"))
    app.run(host=host, port=port, threaded=True)

#!/usr/bin/python3
"""RESTful API views for HistoricalEvent objects: notable events pinned
to a place and a year, shown as markers on the historical-imagery
timeline in the frontend.

Reads are public (same as regions/cities); writes require an admin
session, enforced by require_admin_for_writes in api/v1/app.py (see
ADMIN_GATED_PREFIXES there) rather than a per-route decorator — same
pattern already used for regions/cities.
"""
from datetime import datetime
from flask import jsonify, abort, request
from api.v1.views import app_views
from models import storage
from models.historical_event import HistoricalEvent
from api.v1.validation import (
    ValidationError,
    require_non_empty_string,
    require_integer_in_range,
    require_number_in_range,
    optional_string,
    optional_url,
    only_allowed_fields,
)

# The Esri Wayback imagery this timeline scrubs through only reaches
# back to ~2014 (see WAYBACK_FALLBACK_MIN_YEAR in frontend/app.js) —
# pinning an event to an earlier year would put it on imagery that
# can't show anything relevant to it, so that's the hard floor here too.
EVENT_YEAR_MIN = 2014

EVENT_FIELDS = {
    "title", "year", "latitude", "longitude", "description", "source_url",
}


def _validate_event_data(data, *, require_required_fields):
    """Validate a HistoricalEvent request body; raises ValidationError
    on failure."""
    only_allowed_fields(data, EVENT_FIELDS)
    if require_required_fields or "title" in data:
        require_non_empty_string(data, "title", max_length=200)
    if require_required_fields or "year" in data:
        require_integer_in_range(
            data, "year", EVENT_YEAR_MIN, datetime.utcnow().year)
    if require_required_fields or "latitude" in data:
        require_number_in_range(data, "latitude", -90, 90)
    if require_required_fields or "longitude" in data:
        require_number_in_range(data, "longitude", -180, 180)
    optional_string(data, "description")
    optional_url(data, "source_url", max_length=500)


def _sorted_by_year(events):
    return sorted(events, key=lambda e: e.year)


@app_views.route("/historical-events", methods=["GET"])
def get_historical_events():
    """Return all HistoricalEvent objects, sorted by year."""
    events = list(storage.all(HistoricalEvent).values())
    return jsonify([e.to_dict() for e in _sorted_by_year(events)])


@app_views.route("/historical-events", methods=["POST"])
def create_historical_event():
    """Create a new HistoricalEvent object."""
    data = request.get_json(silent=True)
    if data is None:
        abort(400, description="Not a JSON")
    try:
        _validate_event_data(data, require_required_fields=True)
    except ValidationError as error:
        abort(400, description=error.message)
    event = HistoricalEvent(**data)
    event.save()
    return jsonify(event.to_dict()), 201


@app_views.route("/historical-events/<event_id>", methods=["PUT"])
def update_historical_event(event_id):
    """Update an existing HistoricalEvent object from a JSON body."""
    event = storage.all(HistoricalEvent).get(
        "HistoricalEvent.{}".format(event_id))
    if event is None:
        abort(404)
    data = request.get_json(silent=True)
    if data is None:
        abort(400, description="Not a JSON")
    try:
        _validate_event_data(data, require_required_fields=False)
    except ValidationError as error:
        abort(400, description=error.message)
    for key, value in data.items():
        setattr(event, key, value)
    event.save()
    return jsonify(event.to_dict()), 200


@app_views.route("/historical-events/<event_id>", methods=["DELETE"])
def delete_historical_event(event_id):
    """Delete a HistoricalEvent object by id, or 404 if not found."""
    event = storage.all(HistoricalEvent).get(
        "HistoricalEvent.{}".format(event_id))
    if event is None:
        abort(404)
    event.delete()
    storage.save()
    return jsonify({}), 200

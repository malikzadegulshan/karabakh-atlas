#!/usr/bin/python3
"""Index view: status and stats endpoints for the API."""
from collections import Counter
from api.v1.views import app_views
from flask import jsonify
from models import storage
from models.region import Region
from models.city import City
from models.historical_event import HistoricalEvent
from models.forum_post import ForumPost


@app_views.route("/status", methods=["GET"])
def status():
    """Return a simple OK status payload."""
    return jsonify({"status": "OK"})


@app_views.route("/stats", methods=["GET"])
def stats():
    """Return public counts for the "about this atlas" dashboard.

    Only ever counts what's already publicly visible elsewhere in the
    API — approved forum posts, not pending/rejected ones — so this
    endpoint can stay unauthenticated without leaking anything a
    moderation-gated view wouldn't otherwise show.
    """
    cities = list(storage.all(City).values())
    pois = [c for c in cities if c.category != "city"]
    # category is validated as non-null on every write path (see
    # _validate_city_data in cities.py) — this only guards against a
    # row that predates that validation, so one bad legacy record can't
    # 500 an otherwise-public, unauthenticated endpoint.
    category_counts = Counter(c.category for c in pois if c.category)
    approved_posts = [
        p for p in storage.all(ForumPost).values() if p.status == "approved"
    ]
    return jsonify({
        "regions": len(storage.all(Region)),
        "cities": len(cities) - len(pois),
        "points_of_interest": len(pois),
        "categories": dict(category_counts),
        "historical_events": len(storage.all(HistoricalEvent)),
        "forum_posts": len(approved_posts),
    })

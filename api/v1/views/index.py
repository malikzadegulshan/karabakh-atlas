#!/usr/bin/python3
"""Index view: status and stats endpoints for the API."""
from collections import Counter
from api.v1.views import app_views
from flask import jsonify, request
from models import storage
from models.region import Region
from models.city import City
from models.historical_event import HistoricalEvent
from models.forum_post import ForumPost

COUNTRY_TO_LANG = {
    "AZ": "az",
    "TR": "tr",
    "RU": "ru",
    "BY": "ru",
}


def country_to_lang(country_code):
    """Map an ISO 3166-1 alpha-2 country code to a supported UI language.

    Azerbaijan -> 'az', Turkiye -> 'tr', Russia/Belarus -> 'ru',
    any other country -> 'en'.
    """
    if not country_code or not isinstance(country_code, str):
        return "en"
    code = country_code.strip().upper()
    return COUNTRY_TO_LANG.get(code, "en")


def detect_request_country():
    """Extract a validated 2-letter ISO country code from CF-IPCountry."""
    raw = (request.headers.get("CF-IPCountry") or "").strip().upper()
    if len(raw) == 2 and raw.isalpha() and raw.isascii() and raw not in {
        "XX",
        "T1",
    }:
        return raw
    return None


@app_views.route("/status", methods=["GET"])
def status():
    """Return status payload along with IP-detected country language."""
    payload = {"status": "OK"}
    country = detect_request_country()
    if country:
        payload["country"] = country
        payload["detected_lang"] = country_to_lang(country)
    resp = jsonify(payload)
    resp.headers["Vary"] = "CF-IPCountry"
    resp.headers["Cache-Control"] = "private, no-store"
    return resp


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

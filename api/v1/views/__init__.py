#!/usr/bin/python3
"""Blueprint aggregating all API v1 view modules."""
from flask import Blueprint

app_views = Blueprint("app_views", __name__, url_prefix="/api/v1")

from api.v1.views.index import *  # noqa: E402,F401,F403
from api.v1.views.regions import *  # noqa: E402,F401,F403
from api.v1.views.cities import *  # noqa: E402,F401,F403
from api.v1.views.auth import *  # noqa: E402,F401,F403
from api.v1.views.forum import *  # noqa: E402,F401,F403
from api.v1.views.historical_events import *  # noqa: E402,F401,F403

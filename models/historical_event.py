#!/usr/bin/python3
"""Defines the HistoricalEvent class — a notable event pinned to a
place and a year, shown as a marker on the historical-imagery timeline.

Scoped to years the underlying satellite imagery can actually back up
(see EVENT_YEAR_MIN in api/v1/views/historical_events.py): the Esri
Wayback basemap only reaches back to ~2014, so events pinned to earlier
years would sit on imagery that can't show anything relevant to them.
"""
from models.base_model import BaseModel, Base
from sqlalchemy import Column, String, Integer, Float, Text, JSON


class HistoricalEvent(BaseModel, Base):
    """A dated, located historical event shown on the timeline."""

    __tablename__ = "historical_events"

    title = Column(String(200), nullable=False)
    year = Column(Integer, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    description = Column(Text, nullable=True)
    source_url = Column(String(500), nullable=True)
    # Optional per-language overrides, e.g. {"az": "...", "tr": "...",
    # "ru": "..."} — same convention as City.name_i18n/description_i18n.
    # `title`/`description` above remain the English fallback when a
    # translation is missing for the requested language.
    title_i18n = Column(JSON, nullable=True)
    description_i18n = Column(JSON, nullable=True)

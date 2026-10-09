#!/usr/bin/python3
"""Defines the NewsItem class — a news post written by an admin and
shown in the News tab (see api/v1/views/news.py)."""
from models.base_model import BaseModel, Base
from sqlalchemy import Column, String, Text, JSON


class NewsItem(BaseModel, Base):
    """A news post: headline, body text, and an optional photo/source."""

    __tablename__ = "news_items"

    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    image_url = Column(String(500), nullable=True)
    source_url = Column(String(500), nullable=True)
    # Optional per-language overrides, e.g. {"az": "...", "tr": "...",
    # "ru": "..."} — same convention as City.name_i18n/description_i18n.
    # `title`/`body` above remain the English fallback when a translation
    # is missing for the requested language.
    title_i18n = Column(JSON, nullable=True)
    body_i18n = Column(JSON, nullable=True)

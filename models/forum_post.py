#!/usr/bin/python3
"""Defines the ForumPost class — a user's opinion about the Karabakh
region, one of its cities, or a point of interest, or a comment on a
news item, held for moderation before it's shown to the public."""
from models.base_model import BaseModel, Base
from sqlalchemy import Column, String, Text, ForeignKey, DateTime

STATUSES = ("pending", "approved", "rejected")


class ForumPost(BaseModel, Base):
    """A user-submitted opinion, awaiting or having received moderation."""

    __tablename__ = "forum_posts"

    author_id = Column(String(60), ForeignKey("users.id"), nullable=False)
    # Null means a general opinion about Karabakh as a whole rather than
    # a specific place — cities and points of interest are both rows in
    # the City table (see models/city.py), so this single nullable
    # column covers "about a city", "about a POI", and "general".
    target_city_id = Column(String(60), ForeignKey("cities.id"), nullable=True)
    # Set instead of target_city_id when this post is a comment on a news
    # item (see api/v1/views/news.py). Comments deliberately reuse
    # ForumPost rather than getting their own table, so they inherit the
    # same moderation queue, rate limit, and author/admin delete rules.
    target_news_id = Column(
        String(60), ForeignKey("news_items.id"), nullable=True)
    body = Column(Text, nullable=False)
    status = Column(String(16), nullable=False, default="pending")
    moderated_by = Column(String(60), ForeignKey("users.id"), nullable=True)
    moderated_at = Column(DateTime, nullable=True)

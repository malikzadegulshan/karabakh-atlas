#!/usr/bin/python3
"""Defines the PostReport class — a logged-in user flagging a forum post
(or reply, or news comment) for an admin to look at."""
from models.base_model import BaseModel, Base
from sqlalchemy import Column, String, ForeignKey

REPORT_REASONS = ("spam", "abusive", "misleading", "other")


class PostReport(BaseModel, Base):
    """One user's report of one post. A user reporting the same post
    twice is collapsed in the view layer (like Favorite), so both
    storage engines enforce the same rule."""

    __tablename__ = "post_reports"

    post_id = Column(String(60), ForeignKey("forum_posts.id"), nullable=False)
    reporter_id = Column(String(60), ForeignKey("users.id"), nullable=False)
    reason = Column(String(16), nullable=False, default="other")

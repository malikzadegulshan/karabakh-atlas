#!/usr/bin/python3
"""Defines the Image class — an uploaded photo's bytes, stored inline
as base64 rather than to local disk.

A disk-backed uploads folder wouldn't survive a redeploy on a host
with an ephemeral filesystem (Render's free web service included), so
this rides the same dual FileStorage/DBStorage persistence every other
model already uses instead of needing separate object-storage
credentials. Deliberately has no foreign key to the City it
illustrates — the same arm's-length relationship an external
image_url already has, so an uploaded image and a pasted URL are
interchangeable from City's point of view (see POST /images in
api/v1/views/images.py, which just hands back a URL for either
image_url or image_url_before to hold).
"""
from models.base_model import BaseModel, Base
from sqlalchemy import Column, String, Text


class Image(BaseModel, Base):
    """An uploaded image, served back out at GET /images/<id>."""

    __tablename__ = "images"

    content_type = Column(String(50), nullable=False)
    data_base64 = Column(Text, nullable=False)

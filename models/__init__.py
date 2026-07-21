#!/usr/bin/python3
"""Instantiate a unique storage instance for the whole application."""
import os

storage_t = os.environ.get("KBA_TYPE_STORAGE", "file")

if storage_t == "db":
    from models.engine.db_storage import DBStorage
    storage = DBStorage()
else:
    from models.engine.file_storage import FileStorage
    storage = FileStorage()

storage.reload()

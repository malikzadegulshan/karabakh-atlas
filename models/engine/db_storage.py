#!/usr/bin/python3
"""Defines DBStorage, a PostgreSQL-backed persistence engine."""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from models.base_model import Base
from models.region import Region
from models.city import City
from models.user import User
from models.forum_post import ForumPost

classes = {
    "Region": Region, "City": City, "User": User, "ForumPost": ForumPost,
}


def _db_url():
    """Build the SQLAlchemy connection URL for the database.

    Prefers DATABASE_URL, the convention most hosting platforms
    (including Render) inject automatically for a provisioned Postgres
    instance. Falls back to individual KBA_DB_* vars for manual/local
    setups. Some platforms still hand out the legacy "postgres://"
    scheme; SQLAlchemy 2.x only accepts "postgresql://", so normalize it.
    """
    url = os.environ.get("DATABASE_URL")
    if url:
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        return url
    user = os.environ.get("KBA_DB_USER")
    pwd = os.environ.get("KBA_DB_PWD")
    host = os.environ.get("KBA_DB_HOST", "localhost")
    db = os.environ.get("KBA_DB_NAME")
    return "postgresql+psycopg2://{}:{}@{}/{}".format(user, pwd, host, db)


class DBStorage:
    """Manages a SQLAlchemy session against a PostgreSQL database."""

    __engine = None
    __session = None

    def __init__(self):
        """Create the SQLAlchemy engine from DATABASE_URL or KBA_DB_* vars."""
        env = os.environ.get("KBA_ENV")
        self.__engine = create_engine(_db_url(), pool_pre_ping=True)
        if env == "test":
            Base.metadata.drop_all(self.__engine)

    def all(self, cls=None):
        """Query all objects, optionally filtered by class."""
        result = {}
        targets = [cls] if cls else list(classes.values())
        for c in targets:
            if isinstance(c, str):
                c = classes.get(c)
            for obj in self.__session.query(c).all():
                result["{}.{}".format(type(obj).__name__, obj.id)] = obj
        return result

    def new(self, obj):
        """Add obj to the current session."""
        self.__session.add(obj)

    def save(self):
        """Commit all changes of the current session."""
        self.__session.commit()

    def delete(self, obj=None):
        """Delete obj from the current session if present."""
        if obj is not None:
            self.__session.delete(obj)

    def reload(self):
        """Create all tables and open a new scoped session."""
        Base.metadata.create_all(self.__engine)
        factory = sessionmaker(bind=self.__engine, expire_on_commit=False)
        self.__session = scoped_session(factory)

    def close(self):
        """Close the current session."""
        self.__session.remove()

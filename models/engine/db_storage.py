#!/usr/bin/python3
"""Defines DBStorage, a PostgreSQL-backed persistence engine."""
import os
import sys
from sqlalchemy import create_engine, inspect, text
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
        """Create all tables, add any columns a model has gained since
        the table was first created, and open a new scoped session."""
        Base.metadata.create_all(self.__engine)
        self._sync_missing_columns()
        factory = sessionmaker(bind=self.__engine, expire_on_commit=False)
        self.__session = scoped_session(factory)

    def _sync_missing_columns(self):
        """Add columns a model declares but an existing table doesn't
        have yet — e.g. after a deploy adds a field to City without a
        migration ever running against this database.

        create_all() above only creates whole tables that don't exist;
        it never alters ones that do, so this is the only thing that
        catches that gap. Strictly additive (ADD COLUMN only, nothing
        ever dropped or changed) and best-effort per column — one
        column failing (e.g. NOT NULL with no default against a
        populated table) is logged and skipped rather than blocking
        every other table/column, or the app, from starting.
        """
        inspector = inspect(self.__engine)
        for table in Base.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue
            existing = {col["name"] for col in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing:
                    continue
                ddl_type = column.type.compile(dialect=self.__engine.dialect)
                try:
                    with self.__engine.begin() as conn:
                        conn.execute(text(
                            'ALTER TABLE "{}" ADD COLUMN "{}" {}'.format(
                                table.name, column.name, ddl_type)
                        ))
                    print(
                        "Added missing column {}.{}".format(
                            table.name, column.name),
                        file=sys.stderr,
                    )
                except Exception as error:
                    print(
                        "WARNING: could not add column {}.{}: {}".format(
                            table.name, column.name, error),
                        file=sys.stderr,
                    )

    def close(self):
        """Close the current session."""
        self.__session.remove()

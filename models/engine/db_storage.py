#!/usr/bin/python3
"""Defines DBStorage, a MySQL-backed persistence engine."""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from models.base_model import Base
from models.region import Region
from models.city import City
from models.user import User

classes = {"Region": Region, "City": City, "User": User}


class DBStorage:
    """Manages a SQLAlchemy session against a MySQL database."""

    __engine = None
    __session = None

    def __init__(self):
        """Create the SQLAlchemy engine from KBA_MYSQL_* env variables."""
        user = os.environ.get("KBA_MYSQL_USER")
        pwd = os.environ.get("KBA_MYSQL_PWD")
        host = os.environ.get("KBA_MYSQL_HOST", "localhost")
        db = os.environ.get("KBA_MYSQL_DB")
        env = os.environ.get("KBA_ENV")
        self.__engine = create_engine(
            "mysql+mysqldb://{}:{}@{}/{}".format(user, pwd, host, db),
            pool_pre_ping=True)
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

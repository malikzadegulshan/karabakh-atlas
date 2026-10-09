#!/usr/bin/python3
"""Unit tests for api.v1.forum_utils."""
import unittest
from unittest import mock
from api.v1.forum_utils import delete_forum_posts, publicly_visible


class _Post:
    def __init__(self, id, parent_id=None, status="approved", log=None):
        self.id = id
        self.parent_id = parent_id
        self.status = status
        self._log = log

    def delete(self):
        self._log.append(self.id)


class TestForumUtils(unittest.TestCase):
    """Replies are removed before the posts they answer."""

    def test_replies_are_committed_before_their_parents_are_deleted(self):
        """A save separates the two groups, so the database sees the
        replies gone before it sees the parent deleted."""
        log = []
        parent = _Post("p", log=log)
        reply = _Post("r", parent_id="p", log=log)
        other = _Post("o", log=log)
        with mock.patch("api.v1.forum_utils.storage") as fake_storage:
            fake_storage.save.side_effect = lambda: log.append("SAVE")
            delete_forum_posts([parent, other, reply])
        self.assertEqual(log[0], "r")
        self.assertEqual(log[1], "SAVE")
        self.assertEqual(sorted(log[2:]), ["o", "p"])

    def test_no_save_when_there_are_no_replies(self):
        log = []
        with mock.patch("api.v1.forum_utils.storage") as fake_storage:
            delete_forum_posts([_Post("a", log=log), _Post("b", log=log)])
        fake_storage.save.assert_not_called()

    def test_visibility_follows_the_parent(self):
        parent = _Post("p")
        reply = _Post("r", parent_id="p")
        by_id = {"p": parent, "r": reply}
        self.assertTrue(publicly_visible(reply, by_id))
        parent.status = "rejected"
        self.assertFalse(publicly_visible(reply, by_id))
        self.assertFalse(publicly_visible(parent, by_id))

    def test_pending_posts_are_not_visible(self):
        self.assertFalse(publicly_visible(_Post("x", status="pending"), {}))

    def test_reply_with_missing_parent_is_not_visible(self):
        self.assertFalse(publicly_visible(_Post("r", parent_id="gone"), {}))


if __name__ == "__main__":
    unittest.main()


class TestAgainstARealForeignKey(unittest.TestCase):
    """The bug only shows up where foreign keys are enforced (PostgreSQL
    in production and CI) — file storage can't catch it — so run the
    helper against SQLite with foreign keys switched on."""

    def test_parent_with_replies_deletes_cleanly(self):
        from sqlalchemy import create_engine, event
        from sqlalchemy.orm import sessionmaker
        from models.base_model import Base
        import models.engine.db_storage  # noqa: F401  registers all models
        from models.forum_post import ForumPost
        from models.user import User

        engine = create_engine("sqlite://")
        event.listen(
            engine, "connect",
            lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
        Base.metadata.create_all(engine)
        session = sessionmaker(bind=engine)()

        user = User(name="u", email="fk@example.com", password_hash="x")
        session.add(user)
        session.commit()
        # Ids chosen so the parent sorts before its reply: SQLAlchemy
        # deletes same-table rows in primary-key order, which is exactly
        # the order that violates the foreign key if done in one flush.
        parent = ForumPost(
            id="aaaa-parent", author_id=user.id, body="p", status="approved")
        reply = ForumPost(
            id="zzzz-reply", author_id=user.id, body="r",
            status="approved", parent_id="aaaa-parent")
        session.add_all([parent, reply])
        session.commit()

        class SessionStorage:
            delete = staticmethod(session.delete)
            save = staticmethod(session.commit)

        with mock.patch("api.v1.forum_utils.storage", SessionStorage), \
                mock.patch("models.storage", SessionStorage):
            delete_forum_posts([parent, reply])
            session.commit()
        self.assertEqual(session.query(ForumPost).count(), 0)

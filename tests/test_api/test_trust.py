#!/usr/bin/python3
"""Tests for the trust basics: reporting posts (and the admin review
list) and users deleting their own accounts."""
import json
import unittest
import uuid
from api.v1.app import app
from api.v1 import auth_utils
from models import storage
from models.favorite import Favorite
from models.city import City
from models.forum_post import ForumPost
from models.post_report import PostReport
from models.region import Region
from models.user import User

PASSWORD = "correcthorsebattery"


def _email():
    return "user-{}@example.com".format(uuid.uuid4())


def _json(client, method, url, payload=None):
    return getattr(client, method)(
        url, data=json.dumps(payload) if payload is not None else None,
        content_type="application/json")


def _reset_limiters():
    for limiter in (auth_utils.login_limiter, auth_utils.register_limiter,
                    auth_utils.forum_post_limiter, auth_utils.report_limiter):
        limiter._attempts.clear()


def _register(name="Reader"):
    client = app.test_client()
    email = _email()
    resp = _json(client, "post", "/api/v1/auth/register", {
        "name": name, "email": email, "password": PASSWORD})
    return client, json.loads(resp.data)["id"], email


def _admin():
    client = app.test_client()
    admin = User(name="Trust Admin", email=_email(), role="admin")
    admin.set_password(PASSWORD)
    admin.save()
    _json(client, "post", "/api/v1/auth/login",
          {"email": admin.email, "password": PASSWORD})
    return client


def _published_post(admin, **extra):
    payload = {"body": "Post {}".format(uuid.uuid4())}
    payload.update(extra)
    resp = _json(admin, "post", "/api/v1/forum/posts", payload)
    return json.loads(resp.data)


class TestReports(unittest.TestCase):
    """Reporting a post and the admin review list."""

    def setUp(self):
        _reset_limiters()
        self.admin = _admin()
        self.post = _published_post(self.admin)

    def _report(self, client, reason=None, post_id=None):
        payload = {"reason": reason} if reason else None
        return _json(client, "post", "/api/v1/forum/posts/{}/report".format(
            post_id or self.post["id"]), payload or {})

    def test_report_requires_login(self):
        self.assertEqual(self._report(app.test_client()).status_code, 401)

    def test_report_creates_one_report_and_repeats_are_noops(self):
        reader, _, _ = _register()
        self.assertEqual(self._report(reader, "spam").status_code, 201)
        self.assertEqual(self._report(reader, "abusive").status_code, 200)
        reports = [r for r in storage.all(PostReport).values()
                   if r.post_id == self.post["id"]]
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0].reason, "spam")

    def test_reason_defaults_to_other_and_must_be_known(self):
        reader, _, _ = _register()
        self.assertEqual(
            _json(reader, "post", "/api/v1/forum/posts/{}/report".format(
                self.post["id"])).status_code, 201)
        other, _, _ = _register()
        self.assertEqual(self._report(other, "nonsense").status_code, 400)
        self.assertEqual(
            _json(other, "post", "/api/v1/forum/posts/{}/report".format(
                self.post["id"]), {"reason": ["spam"]}).status_code, 400)

    def test_cannot_report_your_own_post(self):
        reader, _, _ = _register()
        own = json.loads(_json(reader, "post", "/api/v1/forum/posts",
                               {"body": "mine"}).data)
        # pending, so approve it first to make it reportable at all
        _json(self.admin, "put",
              "/api/v1/forum/posts/{}/status".format(own["id"]),
              {"status": "approved"})
        self.assertEqual(
            self._report(reader, "spam", own["id"]).status_code, 400)

    def test_unpublished_or_missing_posts_answer_404(self):
        reader, _, _ = _register()
        pending = json.loads(_json(
            _register()[0], "post", "/api/v1/forum/posts",
            {"body": "pending"}).data)
        self.assertEqual(self._report(reader, post_id=pending["id"])
                         .status_code, 404)
        self.assertEqual(self._report(reader, post_id="nope").status_code, 404)

    def test_admin_list_counts_and_orders_reports(self):
        popular = _published_post(self.admin)
        for index in range(3):
            reader, _, _ = _register()
            self._report(reader, "spam" if index < 2 else "abusive",
                         popular["id"])
        reader, _, _ = _register()
        self._report(reader, "other")

        listing = json.loads(self.admin.get("/api/v1/forum/reports").data)
        ids = [entry["post"]["id"] for entry in listing]
        self.assertLess(ids.index(popular["id"]), ids.index(self.post["id"]))
        entry = listing[ids.index(popular["id"])]
        self.assertEqual(entry["report_count"], 3)
        self.assertEqual(entry["reasons"], {"spam": 2, "abusive": 1})

    def test_report_list_and_dismiss_are_admin_only(self):
        reader, _, _ = _register()
        self._report(reader, "spam")
        for client in (app.test_client(), reader):
            self.assertIn(
                client.get("/api/v1/forum/reports").status_code, (401, 403))
            self.assertIn(
                client.delete("/api/v1/forum/reports/{}".format(
                    self.post["id"])).status_code, (401, 403))

    def test_dismiss_clears_reports_but_keeps_the_post(self):
        reader, _, _ = _register()
        self._report(reader, "spam")
        resp = self.admin.delete(
            "/api/v1/forum/reports/{}".format(self.post["id"]))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse([r for r in storage.all(PostReport).values()
                          if r.post_id == self.post["id"]])
        self.assertIn("ForumPost.{}".format(self.post["id"]),
                      storage.all(ForumPost))
        self.assertEqual(self.admin.delete(
            "/api/v1/forum/reports/{}".format(self.post["id"])).status_code,
            404)

    def test_deleting_a_post_deletes_its_reports(self):
        reader, _, _ = _register()
        self._report(reader, "spam")
        self.admin.delete("/api/v1/forum/posts/{}".format(self.post["id"]))
        self.assertFalse([r for r in storage.all(PostReport).values()
                          if r.post_id == self.post["id"]])

    def test_reports_are_rate_limited(self):
        reader, _, _ = _register()
        last = None
        for _ in range(auth_utils.report_limiter.max_attempts + 1):
            last = self._report(reader, "spam", _published_post(
                self.admin)["id"]).status_code
        self.assertEqual(last, 429)


class TestAccountDeletion(unittest.TestCase):
    """DELETE /auth/account removes the user and everything they own."""

    def setUp(self):
        _reset_limiters()
        self.admin = _admin()

    def _delete(self, client, password=PASSWORD):
        return _json(client, "delete", "/api/v1/auth/account",
                     {"password": password})

    def test_requires_login(self):
        self.assertEqual(self._delete(app.test_client()).status_code, 401)

    def test_wrong_password_deletes_nothing(self):
        reader, user_id, _ = _register()
        self.assertEqual(self._delete(reader, "wrong-password").status_code,
                         401)
        self.assertIn("User.{}".format(user_id), storage.all(User))
        self.assertEqual(reader.get("/api/v1/auth/me").status_code, 200)

    def test_missing_password_or_bad_body_is_400(self):
        reader, _, _ = _register()
        self.assertEqual(
            _json(reader, "delete", "/api/v1/auth/account", {}).status_code,
            400)
        self.assertEqual(
            _json(reader, "delete", "/api/v1/auth/account",
                  ["x"]).status_code, 400)

    def test_wrong_password_attempts_are_rate_limited(self):
        reader, _, _ = _register()
        last = None
        for _ in range(auth_utils.LOGIN_MAX_ATTEMPTS + 1):
            last = self._delete(reader, "wrong-password").status_code
        self.assertEqual(last, 429)

    def test_admin_accounts_cannot_be_deleted(self):
        self.assertEqual(self._delete(self.admin).status_code, 403)

    def test_deletes_account_posts_replies_favorites_and_reports(self):
        leaver, leaver_id, _ = _register("Leaver")
        other, other_id, _ = _register("Other")

        # leaver's post (approved), another user's reply to it, leaver's
        # reply to someone else's post, and a report each way
        mine = json.loads(_json(leaver, "post", "/api/v1/forum/posts",
                                {"body": "leaver post"}).data)
        _json(self.admin, "put", "/api/v1/forum/posts/{}/status".format(
            mine["id"]), {"status": "approved"})
        theirs = _published_post(self.admin)
        reply_to_mine = _published_post(self.admin, parent_id=mine["id"])
        leaver_reply = json.loads(_json(
            leaver, "post", "/api/v1/forum/posts",
            {"body": "leaver reply", "parent_id": theirs["id"]}).data)
        _json(other, "post", "/api/v1/forum/posts/{}/report".format(
            mine["id"]), {"reason": "spam"})
        _json(leaver, "post", "/api/v1/forum/posts/{}/report".format(
            theirs["id"]), {"reason": "spam"})
        favorite = Favorite(user_id=leaver_id, city_id="some-city")
        favorite.save()

        resp = self._delete(leaver)
        self.assertEqual(resp.status_code, 200)

        self.assertNotIn("User.{}".format(leaver_id), storage.all(User))
        self.assertEqual(leaver.get("/api/v1/auth/me").status_code, 401)
        posts = storage.all(ForumPost)
        for gone in (mine["id"], reply_to_mine["id"], leaver_reply["id"]):
            self.assertNotIn("ForumPost.{}".format(gone), posts)
        self.assertIn("ForumPost.{}".format(theirs["id"]), posts)
        self.assertFalse([r for r in storage.all(PostReport).values()
                          if r.reporter_id == leaver_id
                          or r.post_id == mine["id"]])
        self.assertFalse([f for f in storage.all(Favorite).values()
                          if f.user_id == leaver_id])
        self.assertIn("User.{}".format(other_id), storage.all(User))

    def test_can_register_again_with_the_same_email(self):
        reader, _, email = _register()
        self._delete(reader)
        resp = _json(app.test_client(), "post", "/api/v1/auth/register", {
            "name": "Back", "email": email, "password": PASSWORD})
        self.assertEqual(resp.status_code, 201)


class TestAgainstARealForeignKey(unittest.TestCase):
    """Foreign keys are only enforced by a real database (PostgreSQL in
    production and CI), so run the deletion code against SQLite with
    foreign keys switched on."""

    def test_account_deletion_respects_foreign_keys(self):
        from unittest import mock
        from sqlalchemy import create_engine, event
        from sqlalchemy.orm import sessionmaker
        from models.base_model import Base
        import models.engine.db_storage  # noqa: F401  registers all models
        from api.v1.views.auth import _delete_user_data

        engine = create_engine("sqlite://")
        event.listen(
            engine, "connect",
            lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
        Base.metadata.create_all(engine)
        session = sessionmaker(bind=engine)()

        class SessionStorage:
            """Just enough of the storage API over one SQL session."""
            delete = staticmethod(session.delete)
            save = staticmethod(session.commit)

            @staticmethod
            def all(cls):
                return {"{}.{}".format(cls.__name__, row.id): row
                        for row in session.query(cls)}

        leaver = User(name="L", email="l@example.com", password_hash="x")
        other = User(name="O", email="o@example.com", password_hash="x")
        region = Region(name="R")
        session.add_all([leaver, other, region])
        session.commit()
        city = City(name="C", region_id=region.id, latitude=1, longitude=1)
        session.add(city)
        session.commit()
        # Ids chosen so every parent sorts before its reply, the order
        # that violates the self-referencing foreign key if deleted in
        # one flush.
        mine = ForumPost(id="a-mine", author_id=leaver.id, body="m",
                         status="approved")
        answer = ForumPost(id="z-answer", author_id=other.id, body="a",
                           status="approved", parent_id="a-mine")
        theirs = ForumPost(id="b-theirs", author_id=other.id, body="t",
                           status="approved")
        own_reply = ForumPost(id="y-own-reply", author_id=leaver.id,
                              body="r", status="approved",
                              parent_id="b-theirs")
        session.add_all([mine, answer, theirs, own_reply])
        session.commit()
        session.add_all([
            PostReport(post_id="a-mine", reporter_id=other.id, reason="spam"),
            PostReport(post_id="b-theirs", reporter_id=leaver.id,
                       reason="spam"),
            Favorite(user_id=leaver.id, city_id=city.id),
        ])
        session.commit()

        with mock.patch("api.v1.views.auth.storage", SessionStorage), \
                mock.patch("api.v1.forum_utils.storage", SessionStorage), \
                mock.patch("models.storage", SessionStorage):
            _delete_user_data(leaver)

        self.assertEqual(
            sorted(p.id for p in session.query(ForumPost)), ["b-theirs"])
        self.assertEqual(session.query(PostReport).count(), 0)
        self.assertEqual(session.query(Favorite).count(), 0)
        self.assertEqual(
            [u.email for u in session.query(User)], ["o@example.com"])


if __name__ == "__main__":
    unittest.main()

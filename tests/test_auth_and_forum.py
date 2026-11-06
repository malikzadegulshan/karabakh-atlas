#!/usr/bin/python3
"""Integration tests for authentication, user moderation/banning,
community forum, post reporting, account deletion, and security hardening."""
from datetime import datetime, timedelta
import json
import unittest
from unittest import mock
from unittest.mock import patch
import uuid
from api.v1.app import app
from api.v1 import auth_utils
from api.v1.forum_utils import delete_forum_posts, publicly_visible
from models import storage
from models.city import City
from models.favorite import Favorite
from models.forum_post import ForumPost
from models.post_report import PostReport
from models.region import Region
from models.user import User

TEST_PASSWORD = "CorrectHorse1!"
PASSWORD = TEST_PASSWORD
NEW_PASSWORD = "AnotherLongPass2!"
EVIL = "https://evil.example"
FRONTEND = "http://localhost:8000"


def register_and_login(client, name, email, password):
    """Give `client` a signed-in, approved regular user."""
    user = User(
        name=name, email=email, role="user", approved=True,
        email_verified=False)
    user.set_password(password)
    user.save()
    return client.post(
        "/api/v1/auth/login",
        data=json.dumps({"email": email, "password": password}),
        content_type="application/json")


def _unique_email():
    return "user-{}@example.com".format(uuid.uuid4())


def _email():
    return _unique_email()


def _post(client, url, payload, headers=None):
    return client.post(
        url, data=json.dumps(payload), content_type="application/json",
        headers=headers or {})


def _json(client, method, url, payload=None):
    return getattr(client, method)(
        url, data=json.dumps(payload) if payload is not None else None,
        content_type="application/json")


def _admin_client():
    client = app.test_client()
    admin = User(name="Hardening Admin", email=_email(), role="admin")
    admin.set_password(TEST_PASSWORD)
    admin.save()
    _post(client, "/api/v1/auth/login",
          {"email": admin.email, "password": TEST_PASSWORD})
    return client


def _reset_limiters():
    for limiter in (auth_utils.login_limiter, auth_utils.login_ip_limiter,
                    auth_utils.register_limiter,
                    auth_utils.forum_post_limiter, auth_utils.report_limiter,
                    auth_utils.image_upload_limiter):
        limiter._attempts.clear()


def _register(name="Reader"):
    client = app.test_client()
    email = _email()
    resp = register_and_login(client, name, email, PASSWORD)
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


class _Post:
    def __init__(self, id, parent_id=None, status="approved", log=None):
        self.id = id
        self.parent_id = parent_id
        self.status = status
        self._log = log

    def delete(self):
        self._log.append(self.id)


class TestAuthViews(unittest.TestCase):
    """End-to-end tests against the /auth/* views."""

    def setUp(self):
        self.client = app.test_client()
        auth_utils.login_limiter._attempts.clear()
        auth_utils.register_limiter._attempts.clear()
        auth_utils.password_reset_request_limiter._attempts.clear()
        auth_utils.password_reset_attempt_limiter._attempts.clear()
        patcher = patch("api.v1.views.auth.send_email", return_value=True)
        self.mock_send_email = patcher.start()
        self.addCleanup(patcher.stop)

    def _register(self, email=None, password=TEST_PASSWORD,
                  join_reason="I love Karabakh and want to contribute."):
        email = email or _unique_email()
        resp = self.client.post(
            "/api/v1/auth/register",
            data=json.dumps({
                "name": "New User", "email": email, "password": password,
                "join_reason": join_reason}),
            content_type="application/json")
        return email, resp

    def _signed_in_user(self, email=None):
        email = email or _unique_email()
        resp = register_and_login(
            self.client, "New User", email, TEST_PASSWORD)
        return email, resp

    def _user(self, email):
        for user in storage.all(User).values():
            if user.email == email:
                return user
        raise AssertionError("no user found for {}".format(email))

    def _login(self, email, password=TEST_PASSWORD):
        return self.client.post(
            "/api/v1/auth/login",
            data=json.dumps({"email": email, "password": password}),
            content_type="application/json")

    def test_register_creates_pending_account_without_logging_in(self):
        email, resp = self._register()
        self.assertEqual(resp.status_code, 201)
        body = json.loads(resp.data)
        self.assertTrue(body["pending_approval"])
        self.assertNotIn("password_hash", body)

        user = self._user(email)
        self.assertIs(user.approved, False)
        self.assertEqual(user.role, "user")
        self.assertEqual(
            user.join_reason, "I love Karabakh and want to contribute.")

        me_resp = self.client.get("/api/v1/auth/me")
        self.assertEqual(me_resp.status_code, 401)

    def test_register_requires_a_join_reason(self):
        for payload in ({}, {"join_reason": "   "}):
            body = {"name": "New User", "email": _unique_email(),
                    "password": TEST_PASSWORD}
            body.update(payload)
            resp = self.client.post(
                "/api/v1/auth/register", data=json.dumps(body),
                content_type="application/json")
            self.assertEqual(resp.status_code, 400)

    def test_register_rejects_overlong_join_reason(self):
        _, resp = self._register(join_reason="x" * 501)
        self.assertEqual(resp.status_code, 400)

    def test_register_sends_no_email(self):
        self._register()
        self.mock_send_email.assert_not_called()

    def test_pending_account_cannot_log_in(self):
        email, _ = self._register()
        resp = self._login(email)
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(json.loads(resp.data)["pending_approval"])
        self.assertEqual(
            self.client.get("/api/v1/auth/me").status_code, 401)

    def test_pending_login_with_wrong_password_looks_like_any_other(self):
        email, _ = self._register()
        self.assertEqual(self._login(email, "wrong-password").status_code,
                         401)

    def test_pending_account_cannot_reset_password_into_a_session(self):
        email, _ = self._register()
        self.mock_send_email.reset_mock()
        resp = self.client.post(
            "/api/v1/auth/forgot-password",
            data=json.dumps({"email": email}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        self.mock_send_email.assert_not_called()
        self.assertIsNone(self._user(email).password_reset_otp)

    def test_account_created_before_approval_existed_can_log_in(self):
        email = _unique_email()
        user = User(name="Old", email=email, role="user")
        user.set_password(TEST_PASSWORD)
        user.save()
        self.assertEqual(self._login(email).status_code, 200)

    def test_approved_account_can_log_in(self):
        email, _ = self._register()
        user = self._user(email)
        user.approved = True
        user.save()
        resp = self._login(email)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(json.loads(resp.data)["email"], email)

    def test_session_of_an_unapproved_user_is_ignored(self):
        email, _ = self._signed_in_user()
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 200)
        user = self._user(email)
        user.approved = False
        user.save()
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 401)

    def test_register_rejects_short_password(self):
        resp = self.client.post(
            "/api/v1/auth/register",
            data=json.dumps(
                {"name": "New User", "email": _unique_email(),
                 "password": "short", "join_reason": "Because"}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 400)

    def test_register_enforces_password_guidelines(self):
        weak_passwords = [
            "alllowercase1!",
            "ALLUPPERCASE1!",
            "NoDigitsHere!!",
            "NoSpecialChar123",
        ]
        for pwd in weak_passwords:
            _, resp = self._register(password=pwd)
            self.assertEqual(resp.status_code, 400)

    def test_register_rejects_invalid_email(self):
        resp = self.client.post(
            "/api/v1/auth/register",
            data=json.dumps(
                {"name": "New User", "email": "not-an-email",
                 "password": TEST_PASSWORD}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 400)

    def test_register_rejects_duplicate_email(self):
        email = _unique_email()
        first = self.client.post(
            "/api/v1/auth/register",
            data=json.dumps(
                {"name": "First", "email": email,
                 "password": TEST_PASSWORD, "join_reason": "Because"}),
            content_type="application/json")
        self.assertEqual(first.status_code, 201)

        second = self.client.post(
            "/api/v1/auth/register",
            data=json.dumps(
                {"name": "Second", "email": email,
                 "password": TEST_PASSWORD, "join_reason": "Because"}),
            content_type="application/json")
        self.assertEqual(second.status_code, 409)

    def test_login_with_correct_credentials(self):
        email = _unique_email()
        self._signed_in_user(email)
        self.client.post("/api/v1/auth/logout")

        resp = self.client.post(
            "/api/v1/auth/login",
            data=json.dumps({"email": email, "password": TEST_PASSWORD}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 200)

    def test_login_with_wrong_password_fails(self):
        email = _unique_email()
        self._signed_in_user(email)
        self.client.post("/api/v1/auth/logout")

        resp = self.client.post(
            "/api/v1/auth/login",
            data=json.dumps({"email": email, "password": "wrong-password"}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 401)

    def test_login_with_unknown_email_fails(self):
        resp = self.client.post(
            "/api/v1/auth/login",
            data=json.dumps(
                {"email": _unique_email(), "password": TEST_PASSWORD}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 401)

    def test_logout_clears_session(self):
        email = _unique_email()
        self._signed_in_user(email)
        self.client.post("/api/v1/auth/logout")

        me_resp = self.client.get("/api/v1/auth/me")
        self.assertEqual(me_resp.status_code, 401)

    def test_me_without_session_is_401(self):
        resp = self.client.get("/api/v1/auth/me")
        self.assertEqual(resp.status_code, 401)

    def test_login_rate_limited_after_repeated_failures(self):
        email = _unique_email()
        self._signed_in_user(email)
        self.client.post("/api/v1/auth/logout")

        last_status = None
        for _ in range(auth_utils.LOGIN_MAX_ATTEMPTS + 1):
            resp = self.client.post(
                "/api/v1/auth/login",
                data=json.dumps(
                    {"email": email, "password": "wrong-password"}),
                content_type="application/json")
            last_status = resp.status_code
        self.assertEqual(last_status, 429)

    def test_register_rate_limited_after_repeated_attempts(self):
        last_status = None
        for _ in range(auth_utils.register_limiter.max_attempts + 1):
            _, resp = self._register()
            last_status = resp.status_code
        self.assertEqual(last_status, 429)

    def _otp_for(self, email):
        for user in storage.all(User).values():
            if user.email == email:
                return user.password_reset_otp
        raise AssertionError("no user found for {}".format(email))

    def test_forgot_password_for_unknown_email_still_returns_200(self):
        resp = self.client.post(
            "/api/v1/auth/forgot-password",
            data=json.dumps({"email": _unique_email()}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        self.mock_send_email.assert_not_called()

    def test_forgot_password_sends_an_otp_email_for_known_email(self):
        email, _ = self._signed_in_user()
        self.mock_send_email.reset_mock()
        resp = self.client.post(
            "/api/v1/auth/forgot-password",
            data=json.dumps({"email": email}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        self.mock_send_email.assert_called_once()
        self.assertEqual(self.mock_send_email.call_args[0][0], email)
        otp = self._otp_for(email)
        self.assertIsNotNone(otp)
        html_body = self.mock_send_email.call_args[1].get("html_body", "")
        self.assertIn(otp, html_body)
        self.assertIn("Karabakh Atlas", html_body)

    def test_forgot_password_rate_limited_after_repeated_requests(self):
        email, _ = self._signed_in_user()
        last_status = None
        limit = auth_utils.password_reset_request_limiter.max_attempts
        for _ in range(limit + 1):
            resp = self.client.post(
                "/api/v1/auth/forgot-password",
                data=json.dumps({"email": email}),
                content_type="application/json")
            last_status = resp.status_code
        self.assertEqual(last_status, 429)

    def test_reset_password_with_correct_otp_succeeds_and_logs_in(self):
        email, _ = self._signed_in_user()
        self.client.post("/api/v1/auth/logout")
        self.client.post(
            "/api/v1/auth/forgot-password",
            data=json.dumps({"email": email}),
            content_type="application/json")
        otp = self._otp_for(email)

        resp = self.client.post(
            "/api/v1/auth/reset-password",
            data=json.dumps(
                {"email": email, "otp": otp, "password": "Newpassword123!"}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("password_hash", json.loads(resp.data))

        me_resp = self.client.get("/api/v1/auth/me")
        self.assertEqual(me_resp.status_code, 200)

    def test_reset_password_actually_changes_the_password(self):
        email, _ = self._signed_in_user()
        self.client.post("/api/v1/auth/logout")
        self.client.post(
            "/api/v1/auth/forgot-password",
            data=json.dumps({"email": email}),
            content_type="application/json")
        otp = self._otp_for(email)
        self.client.post(
            "/api/v1/auth/reset-password",
            data=json.dumps(
                {"email": email, "otp": otp, "password": "Newpassword123!"}),
            content_type="application/json")
        self.client.post("/api/v1/auth/logout")

        old_resp = self.client.post(
            "/api/v1/auth/login",
            data=json.dumps({"email": email, "password": TEST_PASSWORD}),
            content_type="application/json")
        self.assertEqual(old_resp.status_code, 401)

        new_resp = self.client.post(
            "/api/v1/auth/login",
            data=json.dumps(
                {"email": email, "password": "Newpassword123!"}),
            content_type="application/json")
        self.assertEqual(new_resp.status_code, 200)

    def test_reset_password_with_wrong_otp_fails(self):
        email, _ = self._signed_in_user()
        self.client.post(
            "/api/v1/auth/forgot-password",
            data=json.dumps({"email": email}),
            content_type="application/json")
        resp = self.client.post(
            "/api/v1/auth/reset-password",
            data=json.dumps({
                "email": email, "otp": "000000",
                "password": "Newpassword123!",
            }),
            content_type="application/json")
        self.assertEqual(resp.status_code, 400)

    def test_reset_password_with_expired_otp_fails(self):
        email, _ = self._signed_in_user()
        self.client.post(
            "/api/v1/auth/forgot-password",
            data=json.dumps({"email": email}),
            content_type="application/json")
        for user in storage.all(User).values():
            if user.email == email:
                user.password_reset_otp_expires_at = (
                    datetime.utcnow() - timedelta(seconds=1))
                user.save()
                break
        otp = self._otp_for(email)
        resp = self.client.post(
            "/api/v1/auth/reset-password",
            data=json.dumps(
                {"email": email, "otp": otp, "password": "Newpassword123!"}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 400)

    def test_reset_password_otp_cannot_be_reused(self):
        email, _ = self._signed_in_user()
        self.client.post(
            "/api/v1/auth/forgot-password",
            data=json.dumps({"email": email}),
            content_type="application/json")
        otp = self._otp_for(email)
        first = self.client.post(
            "/api/v1/auth/reset-password",
            data=json.dumps(
                {"email": email, "otp": otp, "password": "Newpassword123!"}),
            content_type="application/json")
        self.assertEqual(first.status_code, 200)

        second = self.client.post(
            "/api/v1/auth/reset-password",
            data=json.dumps(
                {"email": email, "otp": otp, "password": "Anotherpass456!"}),
            content_type="application/json")
        self.assertEqual(second.status_code, 400)

    def test_reset_password_rejects_short_new_password(self):
        email, _ = self._signed_in_user()
        self.client.post(
            "/api/v1/auth/forgot-password",
            data=json.dumps({"email": email}),
            content_type="application/json")
        otp = self._otp_for(email)
        resp = self.client.post(
            "/api/v1/auth/reset-password",
            data=json.dumps({"email": email, "otp": otp, "password": "x"}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 400)

    def test_reset_password_rate_limited_after_repeated_attempts(self):
        email, _ = self._signed_in_user()
        self.client.post(
            "/api/v1/auth/forgot-password",
            data=json.dumps({"email": email}),
            content_type="application/json")
        last_status = None
        limit = auth_utils.password_reset_attempt_limiter.max_attempts
        for _ in range(limit + 1):
            resp = self.client.post(
                "/api/v1/auth/reset-password",
                data=json.dumps({
                    "email": email, "otp": "000000",
                    "password": "Newpassword123!",
                }),
                content_type="application/json")
            last_status = resp.status_code
        self.assertEqual(last_status, 429)

    def test_status_detects_country_language(self):
        """GET /api/v1/status maps CF-IPCountry to az/tr/ru/en."""
        cases = [
            ("AZ", "az"),
            ("az", "az"),
            ("TR", "tr"),
            ("RU", "ru"),
            ("BY", "ru"),
            ("US", "en"),
            ("DE", "en"),
            ("GE", "en"),
        ]
        for country, expected_lang in cases:
            resp = self.client.get(
                "/api/v1/status", headers={"CF-IPCountry": country}
            )
            self.assertEqual(resp.status_code, 200)
            body = resp.get_json()
            self.assertEqual(body["status"], "OK")
            self.assertEqual(body["country"], country.upper())
            self.assertEqual(body["detected_lang"], expected_lang)

        for unknown in ["", "XX", "T1", "INVALID"]:
            resp = self.client.get(
                "/api/v1/status", headers={"CF-IPCountry": unknown}
            )
            self.assertEqual(resp.status_code, 200)
            body = resp.get_json()
            self.assertEqual(body, {"status": "OK"})
            self.assertEqual(resp.headers.get("Vary"), "CF-IPCountry")
            self.assertEqual(
                resp.headers.get("Cache-Control"), "private, no-store"
            )

    def test_forgot_password_does_not_overwrite_stored_user_lang(self):
        """Unauthenticated forgot-password cannot mutate user.lang in DB."""
        email, _ = self._signed_in_user()
        user = self._user(email)
        user.lang = "az"
        user.save()
        resp = self.client.post(
            "/api/v1/auth/forgot-password",
            data=json.dumps({"email": email, "lang": "ru"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._user(email).lang, "az")


class TestUserApproval(unittest.TestCase):
    """Listing, approving, rejecting, and banning accounts."""

    def setUp(self):
        auth_utils.login_limiter._attempts.clear()
        auth_utils.register_limiter._attempts.clear()
        patcher = patch("api.v1.views.users.send_email", return_value=True)
        self.mock_send_email = patcher.start()
        self.addCleanup(patcher.stop)

        self.admin = app.test_client()
        admin = User(
            name="Approval Admin", email=_email(), role="admin",
            approved=True)
        admin.set_password(PASSWORD)
        admin.save()
        self._login(self.admin, admin.email)

        self.pending_email = _email()
        resp = app.test_client().post(
            "/api/v1/auth/register",
            data=json.dumps({
                "name": "Applicant", "email": self.pending_email,
                "password": PASSWORD, "join_reason": "Local historian"}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 201)
        self.pending = [u for u in storage.all(User).values()
                        if u.email == self.pending_email][0]

    def _login(self, client, email):
        return client.post(
            "/api/v1/auth/login",
            data=json.dumps({"email": email, "password": PASSWORD}),
            content_type="application/json")

    def test_admin_sees_pending_account_with_reason(self):
        resp = self.admin.get("/api/v1/users/pending")
        self.assertEqual(resp.status_code, 200)
        entry = [u for u in json.loads(resp.data)
                 if u["id"] == self.pending.id][0]
        self.assertEqual(entry["email"], self.pending_email)
        self.assertEqual(entry["join_reason"], "Local historian")
        self.assertNotIn("password_hash", entry)

    def test_approved_accounts_are_not_listed(self):
        regular = app.test_client()
        register_and_login(regular, "Member", _email(), PASSWORD)
        ids = [u["id"] for u in json.loads(
            self.admin.get("/api/v1/users/pending").data)]
        self.assertNotIn(
            [u for u in storage.all(User).values()
             if u.name == "Member"][0].id, ids)

    def test_anonymous_and_regular_users_are_refused(self):
        anon = app.test_client()
        self.assertEqual(anon.get("/api/v1/users/pending").status_code, 401)
        regular = app.test_client()
        register_and_login(regular, "Member", _email(), PASSWORD)
        url = "/api/v1/users/{}/approve".format(self.pending.id)
        self.assertEqual(
            regular.get("/api/v1/users/pending").status_code, 403)
        self.assertEqual(regular.post(url).status_code, 403)
        self.assertEqual(anon.post(url).status_code, 401)
        self.assertIs(self.pending.approved, False)

    def test_approving_lets_the_user_log_in(self):
        client = app.test_client()
        self.assertEqual(
            self._login(client, self.pending_email).status_code, 403)
        resp = self.admin.post(
            "/api/v1/users/{}/approve".format(self.pending.id))
        self.assertEqual(resp.status_code, 200)
        self.mock_send_email.assert_called_once()
        self.assertEqual(
            self.mock_send_email.call_args[0][0], self.pending_email)
        html_body = self.mock_send_email.call_args[1].get("html_body", "")
        self.assertIn("Welcome to the Community", html_body)
        self.assertIn("Applicant", html_body)
        self.assertEqual(
            self._login(client, self.pending_email).status_code, 200)

    def test_rejecting_deletes_the_account_and_allows_reapplying(self):
        resp = self.admin.delete(
            "/api/v1/users/{}/reject".format(self.pending.id))
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(
            "User.{}".format(self.pending.id), storage.all(User))
        self.assertEqual(
            self._login(app.test_client(), self.pending_email).status_code,
            401)

    def test_unknown_id_is_404(self):
        self.assertEqual(
            self.admin.post("/api/v1/users/nope/approve").status_code, 404)
        self.assertEqual(
            self.admin.delete("/api/v1/users/nope/reject").status_code, 404)

    def test_already_approved_accounts_cannot_be_rejected(self):
        regular = app.test_client()
        register_and_login(regular, "Member", _email(), PASSWORD)
        member = [u for u in storage.all(User).values()
                  if u.name == "Member"][0]
        resp = self.admin.delete(
            "/api/v1/users/{}/reject".format(member.id))
        self.assertEqual(resp.status_code, 404)
        self.assertIn("User.{}".format(member.id), storage.all(User))

    def test_ban_revokes_session_purges_posts_and_unban_restores(self):
        member_client = app.test_client()
        member_email = _email()
        register_and_login(
            member_client, "RuleBreaker", member_email, PASSWORD
        )
        member = [
            u for u in storage.all(User).values() if u.email == member_email
        ][0]
        post = ForumPost(
            author_id=member.id, body="Spam post", status="approved"
        )
        post.save()

        ban_resp = self.admin.post("/api/v1/users/{}/ban".format(member.id))
        self.assertEqual(ban_resp.status_code, 200)
        self.assertTrue(ban_resp.get_json()["banned"])

        self.assertEqual(
            member_client.get("/api/v1/auth/me").status_code, 401
        )
        login_resp = self._login(app.test_client(), member_email)
        self.assertEqual(login_resp.status_code, 403)
        self.assertTrue(login_resp.get_json()["banned"])
        self.assertNotIn(
            "ForumPost.{}".format(post.id), storage.all(ForumPost)
        )

        unban_resp = self.admin.post(
            "/api/v1/users/{}/unban".format(member.id)
        )
        self.assertEqual(unban_resp.status_code, 200)
        self.assertFalse(unban_resp.get_json()["banned"])
        self.assertEqual(
            self._login(app.test_client(), member_email).status_code, 200
        )

    def test_admin_accounts_cannot_be_banned(self):
        other_admin = User(
            name="Second Admin", email=_email(), role="admin", approved=True
        )
        other_admin.set_password(PASSWORD)
        other_admin.save()
        resp = self.admin.post("/api/v1/users/{}/ban".format(other_admin.id))
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(other_admin.is_banned)


class TestForumViews(unittest.TestCase):
    """End-to-end tests for /forum/posts views."""

    def setUp(self):
        auth_utils.forum_post_limiter._attempts.clear()
        auth_utils.login_limiter._attempts.clear()
        auth_utils.register_limiter._attempts.clear()

        self.client = app.test_client()
        self.user_email = _unique_email()
        resp = register_and_login(
            self.client, "Forum User",
            self.user_email, TEST_PASSWORD)
        self.user_id = json.loads(resp.data)["id"]

        self.admin_client = app.test_client()
        admin = User(
            name="Test Admin", email=_unique_email(), role="admin")
        admin.set_password(TEST_PASSWORD)
        admin.save()
        self.admin_id = admin.id
        self.admin_client.post(
            "/api/v1/auth/login",
            data=json.dumps(
                {"email": admin.email, "password": TEST_PASSWORD}),
            content_type="application/json")

    def _create_post(self, client=None, body="This region is beautiful.",
                     target_city_id=None):
        client = client or self.client
        payload = {"body": body}
        if target_city_id is not None:
            payload["target_city_id"] = target_city_id
        return client.post(
            "/api/v1/forum/posts",
            data=json.dumps(payload),
            content_type="application/json")

    def test_create_requires_login(self):
        anon = app.test_client()
        resp = self._create_post(client=anon)
        self.assertEqual(resp.status_code, 401)

    def test_create_starts_pending(self):
        resp = self._create_post()
        self.assertEqual(resp.status_code, 201)
        body = json.loads(resp.data)
        self.assertEqual(body["status"], "pending")
        self.assertEqual(body["author_id"], self.user_id)

    def test_admin_post_is_auto_approved(self):
        resp = self._create_post(
            client=self.admin_client, body="Admin opinion")
        self.assertEqual(resp.status_code, 201)
        body = json.loads(resp.data)
        self.assertEqual(body["status"], "approved")
        self.assertEqual(body["moderated_by"], self.admin_id)
        self.assertIsNotNone(body["moderated_at"])

        public_bodies = [
            p["body"] for p in
            json.loads(self.client.get("/api/v1/forum/posts").data)]
        self.assertIn("Admin opinion", public_bodies)

    def test_admin_posting_is_not_rate_limited(self):
        limit = auth_utils.forum_post_limiter.max_attempts
        last_status = None
        for _ in range(limit + 2):
            last_status = self._create_post(
                client=self.admin_client).status_code
        self.assertEqual(last_status, 201)

    def test_create_rejects_empty_body(self):
        resp = self._create_post(body="   ")
        self.assertEqual(resp.status_code, 400)

    def test_create_rejects_body_over_max_length(self):
        resp = self._create_post(body="x" * 2001)
        self.assertEqual(resp.status_code, 400)

    def test_create_rejects_status_field_tampering(self):
        resp = self.client.post(
            "/api/v1/forum/posts",
            data=json.dumps({"body": "Nice place.", "status": "approved"}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 400)

    def test_create_rejects_author_id_field_tampering(self):
        resp = self.client.post(
            "/api/v1/forum/posts",
            data=json.dumps(
                {"body": "Nice place.", "author_id": "someone-else"}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 400)

    def test_create_rejects_nonexistent_target_city(self):
        resp = self._create_post(target_city_id="not-a-real-city-id")
        self.assertEqual(resp.status_code, 400)

    def test_create_rejects_html_script_payload(self):
        payload = "<script>alert(1)</script>"
        resp = self._create_post(body=payload)
        self.assertEqual(resp.status_code, 400)

    def test_create_is_rate_limited(self):
        last_status = None
        limit = auth_utils.forum_post_limiter.max_attempts
        for _ in range(limit + 1):
            last_status = self._create_post().status_code
        self.assertEqual(last_status, 429)

    def test_pending_post_not_publicly_visible(self):
        self._create_post(body="Should stay hidden")
        resp = self.client.get("/api/v1/forum/posts")
        bodies = [p["body"] for p in json.loads(resp.data)]
        self.assertNotIn("Should stay hidden", bodies)

    def test_mine_shows_own_pending_post(self):
        self._create_post(body="My own pending opinion")
        resp = self.client.get("/api/v1/forum/posts?mine=true")
        bodies = [p["body"] for p in json.loads(resp.data)]
        self.assertIn("My own pending opinion", bodies)

    def test_mine_requires_login(self):
        anon = app.test_client()
        resp = anon.get("/api/v1/forum/posts?mine=true")
        self.assertEqual(resp.status_code, 401)

    def test_status_filter_ignored_for_non_admin(self):
        self._create_post(body="Sneaky pending read attempt")
        resp = self.client.get("/api/v1/forum/posts?status=pending")
        bodies = [p["body"] for p in json.loads(resp.data)]
        self.assertNotIn("Sneaky pending read attempt", bodies)

    def test_status_filter_works_for_admin(self):
        self._create_post(body="Awaiting review")
        resp = self.admin_client.get("/api/v1/forum/posts?status=pending")
        bodies = [p["body"] for p in json.loads(resp.data)]
        self.assertIn("Awaiting review", bodies)

    def test_approved_post_is_publicly_visible(self):
        create_resp = self._create_post(body="Now approved")
        post_id = json.loads(create_resp.data)["id"]
        approve_resp = self.admin_client.put(
            "/api/v1/forum/posts/{}/status".format(post_id),
            data=json.dumps({"status": "approved"}),
            content_type="application/json")
        self.assertEqual(approve_resp.status_code, 200)

        resp = self.client.get("/api/v1/forum/posts")
        bodies = [p["body"] for p in json.loads(resp.data)]
        self.assertIn("Now approved", bodies)

    def test_rejected_post_stays_hidden(self):
        create_resp = self._create_post(body="Should be rejected")
        post_id = json.loads(create_resp.data)["id"]
        reject_resp = self.admin_client.put(
            "/api/v1/forum/posts/{}/status".format(post_id),
            data=json.dumps({"status": "rejected"}),
            content_type="application/json")
        self.assertEqual(reject_resp.status_code, 200)
        body = json.loads(reject_resp.data)
        self.assertEqual(body["moderated_by"], self.admin_id)
        self.assertIsNotNone(body["moderated_at"])

        resp = self.client.get("/api/v1/forum/posts")
        bodies = [p["body"] for p in json.loads(resp.data)]
        self.assertNotIn("Should be rejected", bodies)

    def test_moderate_requires_admin(self):
        create_resp = self._create_post()
        post_id = json.loads(create_resp.data)["id"]
        resp = self.client.put(
            "/api/v1/forum/posts/{}/status".format(post_id),
            data=json.dumps({"status": "approved"}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 403)

    def test_moderate_requires_login(self):
        create_resp = self._create_post()
        post_id = json.loads(create_resp.data)["id"]
        anon = app.test_client()
        resp = anon.put(
            "/api/v1/forum/posts/{}/status".format(post_id),
            data=json.dumps({"status": "approved"}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 401)

    def test_author_can_delete_own_post(self):
        create_resp = self._create_post()
        post_id = json.loads(create_resp.data)["id"]
        resp = self.client.delete("/api/v1/forum/posts/{}".format(post_id))
        self.assertEqual(resp.status_code, 200)

    def test_other_user_cannot_delete_post(self):
        create_resp = self._create_post()
        post_id = json.loads(create_resp.data)["id"]

        other_client = app.test_client()
        register_and_login(
            other_client, "Other User",
            _unique_email(), TEST_PASSWORD)
        resp = other_client.delete("/api/v1/forum/posts/{}".format(post_id))
        self.assertEqual(resp.status_code, 403)

    def test_admin_can_delete_any_post(self):
        create_resp = self._create_post()
        post_id = json.loads(create_resp.data)["id"]
        resp = self.admin_client.delete(
            "/api/v1/forum/posts/{}".format(post_id))
        self.assertEqual(resp.status_code, 200)

    def _create_city(self):
        region = json.loads(self.admin_client.post(
            "/api/v1/regions",
            data=json.dumps({"name": "Region-{}".format(uuid.uuid4())}),
            content_type="application/json").data)
        city = json.loads(self.admin_client.post(
            "/api/v1/regions/{}/cities".format(region["id"]),
            data=json.dumps(
                {"name": "City", "latitude": 39.8, "longitude": 46.75}),
            content_type="application/json").data)
        return city["id"]

    def test_city_scoped_post_only_shows_under_that_city(self):
        city_id = self._create_city()
        create_resp = self._create_post(
            body="About this city", target_city_id=city_id)
        post_id = json.loads(create_resp.data)["id"]
        self.admin_client.put(
            "/api/v1/forum/posts/{}/status".format(post_id),
            data=json.dumps({"status": "approved"}),
            content_type="application/json")

        general_bodies = [
            p["body"] for p in
            json.loads(self.client.get("/api/v1/forum/posts").data)]
        self.assertNotIn("About this city", general_bodies)

        city_bodies = [
            p["body"] for p in json.loads(self.client.get(
                "/api/v1/forum/posts?city_id={}".format(city_id)).data)]
        self.assertIn("About this city", city_bodies)

    def _post_in_topic(self, topic, body=None):
        payload = {"body": body or "Topic post {}".format(uuid.uuid4())}
        if topic is not None:
            payload["topic"] = topic
        return self.admin_client.post(
            "/api/v1/forum/posts",
            data=json.dumps(payload),
            content_type="application/json")

    def test_post_defaults_to_general_topic(self):
        resp = self._post_in_topic(None)
        self.assertEqual(json.loads(resp.data)["topic"], "general")

    def test_post_keeps_chosen_topic(self):
        for topic in ("global", "student_life", "about_karabakh",
                      "events_holidays", "introductions"):
            resp = self._post_in_topic(topic)
            self.assertEqual(resp.status_code, 201)
            self.assertEqual(json.loads(resp.data)["topic"], topic)

    def test_unknown_topic_is_rejected(self):
        self.assertEqual(self._post_in_topic("politics").status_code, 400)

    def test_topic_rejected_on_place_post(self):
        city = json.loads(self.admin_client.get("/api/v1/cities").data)
        if not city:
            self.skipTest("no city available")
        resp = self.client.post(
            "/api/v1/forum/posts",
            data=json.dumps({
                "body": "About a place", "topic": "global",
                "target_city_id": city[0]["id"]}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 400)

    def test_list_filters_by_topic(self):
        tag = str(uuid.uuid4())
        self._post_in_topic("global", body="Global {}".format(tag))
        self._post_in_topic("introductions", body="Intro {}".format(tag))
        legacy = ForumPost(
            author_id=self.admin_id, body="Legacy {}".format(tag),
            status="approved", topic=None)
        legacy.save()

        def bodies(topic):
            resp = self.client.get("/api/v1/forum/posts?topic=" + topic)
            return [p["body"] for p in json.loads(resp.data)
                    if tag in p["body"]]

        self.assertEqual(bodies("global"), ["Global {}".format(tag)])
        self.assertEqual(bodies("introductions"), ["Intro {}".format(tag)])
        self.assertEqual(bodies("general"), ["Legacy {}".format(tag)])

    def test_invalid_topic_filter_is_rejected(self):
        resp = self.client.get("/api/v1/forum/posts?topic=nope")
        self.assertEqual(resp.status_code, 400)

    def _approved_post(self, **payload):
        payload.setdefault("body", "Post {}".format(uuid.uuid4()))
        resp = self.admin_client.post(
            "/api/v1/forum/posts", data=json.dumps(payload),
            content_type="application/json")
        self.assertEqual(resp.status_code, 201)
        return json.loads(resp.data)

    def _reply(self, client, parent_id, body=None):
        return client.post(
            "/api/v1/forum/posts",
            data=json.dumps({
                "body": body or "Reply {}".format(uuid.uuid4()),
                "parent_id": parent_id}),
            content_type="application/json")

    def _approve(self, post_id, status="approved"):
        return self.admin_client.put(
            "/api/v1/forum/posts/{}/status".format(post_id),
            data=json.dumps({"status": status}),
            content_type="application/json")

    def test_reply_requires_login(self):
        parent = self._approved_post()
        resp = self._reply(app.test_client(), parent["id"])
        self.assertEqual(resp.status_code, 401)

    def test_reply_is_moderated_and_inherits_topic(self):
        parent = self._approved_post(topic="student_life")
        text = "My reply {}".format(uuid.uuid4())
        resp = self._reply(self.client, parent["id"], body=text)
        self.assertEqual(resp.status_code, 201)
        reply = json.loads(resp.data)
        self.assertEqual(reply["status"], "pending")
        self.assertEqual(reply["parent_id"], parent["id"])
        self.assertEqual(reply["topic"], "student_life")

        def public_bodies():
            listing = self.client.get(
                "/api/v1/forum/posts?topic=student_life")
            return [p["body"] for p in json.loads(listing.data)]

        self.assertNotIn(text, public_bodies())
        self._approve(reply["id"])
        self.assertIn(text, public_bodies())

    def test_reply_to_a_reply_attaches_to_the_top_level_post(self):
        parent = self._approved_post()
        first = self._approved_post(parent_id=parent["id"])
        second = self._approved_post(parent_id=first["id"])
        self.assertEqual(first["parent_id"], parent["id"])
        self.assertEqual(second["parent_id"], parent["id"])

    def test_reply_cannot_choose_its_own_target_or_topic(self):
        parent = self._approved_post()
        for extra in ({"topic": "global"}, {"target_city_id": "x"},
                      {"target_news_id": "x"}):
            payload = {"body": "r", "parent_id": parent["id"]}
            payload.update(extra)
            resp = self.client.post(
                "/api/v1/forum/posts", data=json.dumps(payload),
                content_type="application/json")
            self.assertEqual(resp.status_code, 400)

    def test_reply_needs_a_published_parent(self):
        self.assertEqual(
            self._reply(self.client, "nope").status_code, 400)
        pending = json.loads(self._create_post().data)
        self.assertEqual(
            self._reply(self.client, pending["id"]).status_code, 400)
        parent = self._approved_post()
        self._approve(parent["id"], "rejected")
        self.assertEqual(
            self._reply(self.client, parent["id"]).status_code, 400)

    def test_rejecting_a_parent_hides_its_replies(self):
        parent = self._approved_post(topic="global")
        reply = self._approved_post(parent_id=parent["id"])

        def public_ids():
            listing = self.client.get("/api/v1/forum/posts?topic=global")
            return [p["id"] for p in json.loads(listing.data)]

        self.assertIn(reply["id"], public_ids())
        self._approve(parent["id"], "rejected")
        self.assertNotIn(reply["id"], public_ids())
        self.assertNotIn(parent["id"], public_ids())

    def test_deleting_a_post_deletes_its_replies(self):
        parent = self._approved_post()
        reply = self._approved_post(parent_id=parent["id"])
        resp = self.admin_client.delete(
            "/api/v1/forum/posts/{}".format(parent["id"]))
        self.assertEqual(resp.status_code, 200)
        stored = storage.all(ForumPost)
        self.assertNotIn("ForumPost.{}".format(parent["id"]), stored)
        self.assertNotIn("ForumPost.{}".format(reply["id"]), stored)

    def test_reply_on_a_place_post_stays_on_that_place(self):
        cities = json.loads(self.admin_client.get("/api/v1/cities").data)
        if not cities:
            self.skipTest("no city available")
        parent = self._approved_post(target_city_id=cities[0]["id"])
        reply = self._approved_post(parent_id=parent["id"])
        self.assertEqual(reply["target_city_id"], cities[0]["id"])
        self.assertIsNone(reply["topic"])
        listing = self.client.get(
            "/api/v1/forum/posts?city_id=" + cities[0]["id"])
        self.assertIn(
            reply["id"], [p["id"] for p in json.loads(listing.data)])

    def test_moderation_card_data_for_a_reply(self):
        parent = self._approved_post(body="Original thought")
        reply = json.loads(self._reply(self.client, parent["id"]).data)
        queue = json.loads(self.admin_client.get(
            "/api/v1/forum/posts?status=pending").data)
        match = [p for p in queue if p["id"] == reply["id"]][0]
        self.assertEqual(match["parent_excerpt"], "Original thought")
        self.assertEqual(match["parent_author_name"], "Test Admin")

    def test_moderation_queue_includes_place_scoped_posts(self):
        city_resp = self.admin_client.get("/api/v1/cities")
        cities = json.loads(city_resp.data)
        if not cities:
            self.skipTest("no city available")
        resp = self._create_post(
            body="Queued place opinion", target_city_id=cities[0]["id"])
        self.assertEqual(resp.status_code, 201)
        queue = json.loads(self.admin_client.get(
            "/api/v1/forum/posts?status=pending").data)
        self.assertIn(
            "Queued place opinion", [p["body"] for p in queue])

    def test_deleting_city_cascades_to_its_forum_posts(self):
        city_id = self._create_city()
        self._create_post(body="About a soon-deleted city",
                          target_city_id=city_id)

        resp = self.admin_client.delete(
            "/api/v1/cities/{}".format(city_id))
        self.assertEqual(resp.status_code, 200)

        mine_bodies = [
            p["body"] for p in
            json.loads(self.client.get(
                "/api/v1/forum/posts?mine=true&city_id={}".format(
                    city_id)).data)]
        self.assertNotIn("About a soon-deleted city", mine_bodies)


class TestForumUtils(unittest.TestCase):
    """Replies are removed before the posts they answer."""

    def test_replies_are_committed_before_their_parents_are_deleted(self):
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


class TestForumUtilsForeignKey(unittest.TestCase):
    """Run delete_forum_posts against SQLite with foreign keys switched on."""

    def test_parent_with_replies_deletes_cleanly(self):
        from sqlalchemy import create_engine, event
        from sqlalchemy.orm import sessionmaker
        from models.base_model import Base
        import models.engine.db_storage  # noqa: F401

        engine = create_engine("sqlite://")
        event.listen(
            engine, "connect",
            lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
        Base.metadata.create_all(engine)
        session = sessionmaker(bind=engine)()

        user = User(name="u", email="fk@example.com", password_hash="x")
        session.add(user)
        session.commit()
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

            @staticmethod
            def all(cls):
                return {"{}.{}".format(cls.__name__, row.id): row
                        for row in session.query(cls)}

        with mock.patch("api.v1.forum_utils.storage", SessionStorage), \
                mock.patch("models.storage", SessionStorage):
            delete_forum_posts([parent, reply])
            session.commit()
        self.assertEqual(session.query(ForumPost).count(), 0)

    def test_post_with_a_report_and_no_replies_deletes_cleanly(self):
        from sqlalchemy import create_engine, event
        from sqlalchemy.orm import sessionmaker
        from models.base_model import Base
        import models.engine.db_storage  # noqa: F401

        engine = create_engine("sqlite://")
        event.listen(
            engine, "connect",
            lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
        Base.metadata.create_all(engine)
        session = sessionmaker(bind=engine)()
        user = User(name="u", email="r@example.com", password_hash="x")
        session.add(user)
        session.commit()
        post = ForumPost(
            id="p1", author_id=user.id, body="b", status="approved")
        session.add(post)
        session.commit()
        session.add(PostReport(
            post_id="p1", reporter_id=user.id, reason="spam"))
        session.commit()

        class SessionStorage:
            delete = staticmethod(session.delete)
            save = staticmethod(session.commit)

            @staticmethod
            def all(cls):
                return {"{}.{}".format(cls.__name__, row.id): row
                        for row in session.query(cls)}

        with mock.patch("api.v1.forum_utils.storage", SessionStorage), \
                mock.patch("models.storage", SessionStorage):
            delete_forum_posts([post])
            session.commit()
        self.assertEqual(session.query(ForumPost).count(), 0)
        self.assertEqual(session.query(PostReport).count(), 0)


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
        region = json.loads(_json(self.admin, "post", "/api/v1/regions", {
            "name": "Region-{}".format(uuid.uuid4())}).data)
        city = json.loads(_json(
            self.admin, "post", "/api/v1/regions/{}/cities".format(
                region["id"]),
            {"name": "City", "latitude": 39.8, "longitude": 46.75}).data)
        self.assertEqual(_json(
            leaver, "post", "/api/v1/favorites",
            {"city_id": city["id"]}).status_code, 201)

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
            "name": "Back", "email": email, "password": PASSWORD,
            "join_reason": "I'm back"})
        self.assertEqual(resp.status_code, 201)


class TestAccountDeletionForeignKey(unittest.TestCase):
    """Run account deletion against SQLite with foreign keys switched on."""

    def test_account_deletion_respects_foreign_keys(self):
        from sqlalchemy import create_engine, event
        from sqlalchemy.orm import sessionmaker
        from models.base_model import Base
        import models.engine.db_storage  # noqa: F401
        from api.v1.views.auth import _delete_user_data

        engine = create_engine("sqlite://")
        event.listen(
            engine, "connect",
            lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
        Base.metadata.create_all(engine)
        session = sessionmaker(bind=engine)()

        class SessionStorage:
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


class TestProxyAwareRateLimiting(unittest.TestCase):
    """The limiter keys on the visitor's IP from X-Forwarded-For."""

    def setUp(self):
        for limiter in (auth_utils.login_limiter,
                        auth_utils.register_limiter):
            limiter._attempts.clear()
        self.email = _email()
        _post(app.test_client(), "/api/v1/auth/register", {
            "name": "Limited", "email": self.email,
            "password": TEST_PASSWORD, "join_reason": "Testing"})

    def _failed_login(self, forwarded_for):
        return _post(
            app.test_client(), "/api/v1/auth/login",
            {"email": self.email, "password": "wrong-password"},
            headers={"X-Forwarded-For": forwarded_for})

    def test_one_visitors_failures_do_not_lock_out_another(self):
        for _ in range(auth_utils.LOGIN_MAX_ATTEMPTS):
            self._failed_login("203.0.113.1")
        self.assertEqual(self._failed_login("203.0.113.1").status_code, 429)
        self.assertEqual(self._failed_login("203.0.113.2").status_code, 401)

    def test_a_client_cannot_spoof_its_way_out_of_the_limit(self):
        for i in range(auth_utils.LOGIN_MAX_ATTEMPTS):
            self._failed_login("10.0.0.{}, 203.0.113.9".format(i))
        resp = self._failed_login("192.0.2.77, 203.0.113.9")
        self.assertEqual(resp.status_code, 429)


class TestSessionRevocationOnPasswordReset(unittest.TestCase):
    """A password reset signs out every other session."""

    def setUp(self):
        for limiter in (auth_utils.login_limiter,
                        auth_utils.register_limiter,
                        auth_utils.password_reset_attempt_limiter):
            limiter._attempts.clear()

    def test_old_cookie_stops_working_after_reset(self):
        email = _email()
        old_device = app.test_client()
        register_and_login(old_device, "Resetter", email, TEST_PASSWORD)
        self.assertEqual(old_device.get("/api/v1/auth/me").status_code, 200)

        user = [u for u in storage.all(User).values()
                if u.email == email][0]
        otp = user.generate_password_reset_otp()
        user.save()
        new_device = app.test_client()
        resp = _post(new_device, "/api/v1/auth/reset-password", {
            "email": email, "otp": otp, "password": NEW_PASSWORD})
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(new_device.get("/api/v1/auth/me").status_code, 200)
        self.assertEqual(old_device.get("/api/v1/auth/me").status_code, 401)

    def test_new_login_after_reset_works(self):
        email = _email()
        register_and_login(
            app.test_client(), "Resetter", email, TEST_PASSWORD)
        user = [u for u in storage.all(User).values()
                if u.email == email][0]
        otp = user.generate_password_reset_otp()
        user.save()
        _post(app.test_client(), "/api/v1/auth/reset-password", {
            "email": email, "otp": otp, "password": NEW_PASSWORD})
        client = app.test_client()
        resp = _post(client, "/api/v1/auth/login",
                     {"email": email, "password": NEW_PASSWORD})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(client.get("/api/v1/auth/me").status_code, 200)


class TestCrossOriginWrites(unittest.TestCase):
    """State-changing requests from another site are refused."""

    def setUp(self):
        auth_utils.login_limiter._attempts.clear()

    def _login(self, origin=None):
        headers = {"Origin": origin} if origin else {}
        return _post(app.test_client(), "/api/v1/auth/login",
                     {"email": "nobody@example.com", "password": "x" * 12},
                     headers=headers)

    def test_foreign_origin_is_blocked(self):
        self.assertEqual(self._login(EVIL).status_code, 403)

    def test_foreign_origin_cannot_upload_as_admin(self):
        admin = _admin_client()
        resp = admin.post(
            "/api/v1/images", data={}, headers={"Origin": EVIL},
            content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 403)

    def test_frontend_origin_is_allowed(self):
        self.assertEqual(self._login(FRONTEND).status_code, 401)

    def test_own_origin_is_allowed(self):
        self.assertEqual(self._login("http://localhost").status_code, 401)

    def test_no_origin_header_is_allowed(self):
        self.assertEqual(self._login().status_code, 401)

    def test_reads_are_not_affected(self):
        resp = app.test_client().get(
            "/api/v1/news", headers={"Origin": EVIL})
        self.assertEqual(resp.status_code, 200)


class TestMalformedBodies(unittest.TestCase):
    """Wrong-shaped JSON is a 400, never a 500."""

    def setUp(self):
        auth_utils.forum_post_limiter._attempts.clear()
        self.admin = _admin_client()

    def test_list_body_is_rejected_everywhere(self):
        for url in ("/api/v1/forum/posts", "/api/v1/favorites",
                    "/api/v1/news", "/api/v1/historical-events",
                    "/api/v1/regions", "/api/v1/auth/login"):
            resp = _post(self.admin, url, ["not", "an", "object"])
            self.assertEqual(resp.status_code, 400, url)

    def test_non_string_topic_is_rejected(self):
        for topic in ([], {}, ["global"], 5):
            resp = _post(self.admin, "/api/v1/forum/posts",
                         {"body": "x", "topic": topic})
            self.assertEqual(resp.status_code, 400, repr(topic))


class TestRegionDeleteCleanup(unittest.TestCase):
    """Deleting a region leaves no favorites pointing at its cities."""

    def test_favorites_of_deleted_cities_are_removed(self):
        admin = _admin_client()
        region = json.loads(_post(admin, "/api/v1/regions", {
            "name": "Region-{}".format(uuid.uuid4())}).data)
        city = json.loads(_post(
            admin, "/api/v1/regions/{}/cities".format(region["id"]),
            {"name": "City", "latitude": 39.8, "longitude": 46.75}).data)
        resp = _post(admin, "/api/v1/favorites", {"city_id": city["id"]})
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(any(
            f.city_id == city["id"] for f in storage.all(Favorite).values()))

        resp = admin.delete("/api/v1/regions/{}".format(region["id"]))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(any(
            f.city_id == city["id"] for f in storage.all(Favorite).values()))


class TestSecurityReviewHardening(unittest.TestCase):
    """Test the newly added security hardening rules."""

    def setUp(self):
        _reset_limiters()

    def test_rate_limiter_memory_bounding_and_cleanup(self):
        """RateLimiter prunes expired keys and caps tracked keys."""
        limiter = auth_utils.RateLimiter(
            max_attempts=3, window_seconds=10, max_tracked_keys=4)
        for i in range(10):
            limiter.record("key-{}".format(i))
        self.assertLessEqual(len(limiter._attempts), 4)

        # Non-existent key check does not pollute _attempts with empty lists
        self.assertFalse(limiter.is_limited("nonexistent-key"))
        self.assertNotIn("nonexistent-key", limiter._attempts)

    def test_login_ip_rate_limiter(self):
        """Aggregate per-IP login limit blocks credential stuffing."""
        client = app.test_client()
        ip = "198.51.100.42"
        # 30 attempts on 30 different accounts should succeed to attempt
        for i in range(30):
            resp = client.post(
                "/api/v1/auth/login",
                data=json.dumps({
                    "email": "target-{}@example.com".format(i),
                    "password": "WrongPassword1!",
                }),
                content_type="application/json",
                environ_base={"REMOTE_ADDR": ip},
            )
            self.assertEqual(resp.status_code, 401)

        # 31st attempt from same IP must hit 429 even with new email
        resp = client.post(
            "/api/v1/auth/login",
            data=json.dumps({
                "email": "target-new@example.com",
                "password": "WrongPassword1!",
            }),
            content_type="application/json",
            environ_base={"REMOTE_ADDR": ip},
        )
        self.assertEqual(resp.status_code, 429)
        self.assertIn(
            "Too many failed login attempts", resp.get_json()["error"])

    def test_general_content_length_limit(self):
        """Endpoints other than /api/v1/images cap body at 1MB."""
        client = app.test_client()
        # Non-image endpoint with body > 1MB but < 5MB (app-wide cap)
        resp = client.post(
            "/api/v1/auth/login",
            data=b"x" * (1024 * 1024 + 100),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 413)

    def test_news_item_safe_text_validation(self):
        """NewsItem rejects HTML/script tags and BiDi characters."""
        admin = _admin_client()
        resp = _post(admin, "/api/v1/news", {
            "title": "Clean Title",
            "body": "Normal body with <script>alert(1)</script>",
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("HTML or script tags", resp.get_json()["error"])

        resp = _post(admin, "/api/v1/news", {
            "title": "Title with \u202e evil",
            "body": "Normal body",
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("bidirectional", resp.get_json()["error"])

    def test_i18n_dict_script_rejection(self):
        """optional_i18n_dict rejects script tags and event handlers."""
        from api.v1.validation import optional_i18n_dict, ValidationError
        data = {"desc_i18n": {"en": "Safe", "az": "<img src=x onerror=1>"}}
        with self.assertRaises(ValidationError):
            optional_i18n_dict(data, "desc_i18n")

        data2 = {"desc_i18n": {"en": "javascript:alert(1)"}}
        with self.assertRaises(ValidationError):
            optional_i18n_dict(data2, "desc_i18n")

    def test_string_control_chars_and_bidi_rejection(self):
        """require_non_empty_string and optional_string reject ctrl/BiDi."""
        from api.v1.validation import (
            require_non_empty_string, optional_string, ValidationError
        )
        with self.assertRaises(ValidationError):
            require_non_empty_string({"k": "Bad \x00 Null"}, "k")
        with self.assertRaises(ValidationError):
            require_non_empty_string({"k": "Bad \u202e BiDi"}, "k")

        with self.assertRaises(ValidationError):
            optional_string({"k": "Bad \x1f Ctrl"}, "k")
        with self.assertRaises(ValidationError):
            optional_string({"k": "Bad \u2067 BiDi"}, "k")

    def test_image_upload_rate_limiting(self):
        """POST /api/v1/images rate limits after 20 uploads."""
        import io
        client = _admin_client()
        # 1x1 GIF bytes
        gif_bytes = (
            b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff"
            b"\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00"
            b"\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
        )
        for i in range(20):
            data = {"file": (io.BytesIO(gif_bytes), "test.gif")}
            resp = client.post(
                "/api/v1/images",
                data=data,
                content_type="multipart/form-data",
            )
            self.assertEqual(resp.status_code, 201)

        # 21st attempt should be 429
        data = {"file": (io.BytesIO(gif_bytes), "test.gif")}
        resp = client.post(
            "/api/v1/images",
            data=data,
            content_type="multipart/form-data",
        )
        self.assertEqual(resp.status_code, 429)
        self.assertIn("Too many image uploads", resp.get_json()["error"])


if __name__ == "__main__":
    unittest.main()

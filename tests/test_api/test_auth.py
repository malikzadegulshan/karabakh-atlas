#!/usr/bin/python3
"""Tests for the /auth/* views (register, login, logout, me, approval)."""
import json
import unittest
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch
from api.v1.app import app
from api.v1 import auth_utils
from models import storage
from models.user import User
from tests.test_api.helpers import register_and_login

TEST_PASSWORD = "correcthorsebattery"


def _unique_email():
    return "user-{}@example.com".format(uuid.uuid4())


class TestAuthViews(unittest.TestCase):
    """End-to-end tests against the Flask test client."""

    def setUp(self):
        """Create a fresh client and reset the in-memory rate limiter.

        send_email is patched everywhere in this class — no test here
        should depend on actual delivery, just on the reset-code logic
        around it.
        """
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
        """Request an account through the API (it starts pending)."""
        email = email or _unique_email()
        resp = self.client.post(
            "/api/v1/auth/register",
            data=json.dumps({
                "name": "New User", "email": email, "password": password,
                "join_reason": join_reason}),
            content_type="application/json")
        return email, resp

    def _signed_in_user(self, email=None):
        """An approved account, signed in on self.client."""
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
        """Registering files a request: no session, account unapproved."""
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
        """A missing or blank reason is rejected."""
        for payload in ({}, {"join_reason": "   "}):
            body = {"name": "New User", "email": _unique_email(),
                    "password": TEST_PASSWORD}
            body.update(payload)
            resp = self.client.post(
                "/api/v1/auth/register", data=json.dumps(body),
                content_type="application/json")
            self.assertEqual(resp.status_code, 400)

    def test_register_rejects_overlong_join_reason(self):
        """The reason is capped at 500 characters."""
        _, resp = self._register(join_reason="x" * 501)
        self.assertEqual(resp.status_code, 400)

    def test_register_sends_no_email(self):
        """Approval is manual, so registering sends nothing."""
        self._register()
        self.mock_send_email.assert_not_called()

    def test_pending_account_cannot_log_in(self):
        """Right password, but not approved yet: 403 and no session."""
        email, _ = self._register()
        resp = self._login(email)
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(json.loads(resp.data)["pending_approval"])
        self.assertEqual(
            self.client.get("/api/v1/auth/me").status_code, 401)

    def test_pending_login_with_wrong_password_looks_like_any_other(self):
        """A wrong password gets the normal 401, so pending accounts
        can't be discovered without knowing the password."""
        email, _ = self._register()
        self.assertEqual(self._login(email, "wrong-password").status_code,
                         401)

    def test_pending_account_cannot_reset_password_into_a_session(self):
        """Pending accounts do not receive password-reset codes."""
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
        """approved=NULL (an old row) counts as approved."""
        email = _unique_email()
        user = User(name="Old", email=email, role="user")
        user.set_password(TEST_PASSWORD)
        user.save()
        self.assertEqual(self._login(email).status_code, 200)

    def test_approved_account_can_log_in(self):
        """Once an admin approves it, login works."""
        email, _ = self._register()
        user = self._user(email)
        user.approved = True
        user.save()
        resp = self._login(email)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(json.loads(resp.data)["email"], email)

    def test_session_of_an_unapproved_user_is_ignored(self):
        """Even an existing session stops working if the account is
        (back to) unapproved."""
        email, _ = self._signed_in_user()
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 200)
        user = self._user(email)
        user.approved = False
        user.save()
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 401)

    def test_register_rejects_short_password(self):
        """Passwords under the minimum length are rejected."""
        resp = self.client.post(
            "/api/v1/auth/register",
            data=json.dumps(
                {"name": "New User", "email": _unique_email(),
                 "password": "short"}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 400)

    def test_register_rejects_invalid_email(self):
        """Malformed email addresses are rejected."""
        resp = self.client.post(
            "/api/v1/auth/register",
            data=json.dumps(
                {"name": "New User", "email": "not-an-email",
                 "password": TEST_PASSWORD}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 400)

    def test_register_rejects_duplicate_email(self):
        """A second registration with the same email is rejected."""
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
        """Logging in with the right password succeeds and sets a session."""
        email = _unique_email()
        self._signed_in_user(email)
        self.client.post("/api/v1/auth/logout")

        resp = self.client.post(
            "/api/v1/auth/login",
            data=json.dumps({"email": email, "password": TEST_PASSWORD}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 200)

    def test_login_with_wrong_password_fails(self):
        """A wrong password is rejected with 401."""
        email = _unique_email()
        self._signed_in_user(email)
        self.client.post("/api/v1/auth/logout")

        resp = self.client.post(
            "/api/v1/auth/login",
            data=json.dumps({"email": email, "password": "wrong-password"}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 401)

    def test_login_with_unknown_email_fails(self):
        """An email with no account gets the same generic error."""
        resp = self.client.post(
            "/api/v1/auth/login",
            data=json.dumps(
                {"email": _unique_email(), "password": TEST_PASSWORD}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 401)

    def test_logout_clears_session(self):
        """After logout, /auth/me is unauthenticated again."""
        email = _unique_email()
        self._signed_in_user(email)
        self.client.post("/api/v1/auth/logout")

        me_resp = self.client.get("/api/v1/auth/me")
        self.assertEqual(me_resp.status_code, 401)

    def test_me_without_session_is_401(self):
        """/auth/me with no session cookie at all returns 401."""
        resp = self.client.get("/api/v1/auth/me")
        self.assertEqual(resp.status_code, 401)

    def test_login_rate_limited_after_repeated_failures(self):
        """Repeated bad-password attempts eventually get rate-limited."""
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
        """Repeated registrations from one source eventually get
        rate-limited, so the admin's approval queue can't be flooded."""
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
        """An unregistered email gets the same 200 as a real one — this
        endpoint can't be used to enumerate accounts."""
        resp = self.client.post(
            "/api/v1/auth/forgot-password",
            data=json.dumps({"email": _unique_email()}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        self.mock_send_email.assert_not_called()

    def test_forgot_password_sends_an_otp_email_for_known_email(self):
        """A registered email gets a reset-code email."""
        email, _ = self._signed_in_user()
        self.mock_send_email.reset_mock()
        resp = self.client.post(
            "/api/v1/auth/forgot-password",
            data=json.dumps({"email": email}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        self.mock_send_email.assert_called_once()
        self.assertEqual(self.mock_send_email.call_args[0][0], email)
        self.assertIsNotNone(self._otp_for(email))

    def test_forgot_password_rate_limited_after_repeated_requests(self):
        """Repeated requests from one source eventually get rate-limited."""
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
        """A valid OTP sets the new password and starts a session."""
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
                {"email": email, "otp": otp, "password": "newpassword123"}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("password_hash", json.loads(resp.data))

        me_resp = self.client.get("/api/v1/auth/me")
        self.assertEqual(me_resp.status_code, 200)

    def test_reset_password_actually_changes_the_password(self):
        """After a reset, the old password no longer works and the new
        one does."""
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
                {"email": email, "otp": otp, "password": "newpassword123"}),
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
                {"email": email, "password": "newpassword123"}),
            content_type="application/json")
        self.assertEqual(new_resp.status_code, 200)

    def test_reset_password_with_wrong_otp_fails(self):
        """An OTP that doesn't match is rejected."""
        email, _ = self._signed_in_user()
        self.client.post(
            "/api/v1/auth/forgot-password",
            data=json.dumps({"email": email}),
            content_type="application/json")
        resp = self.client.post(
            "/api/v1/auth/reset-password",
            data=json.dumps({
                "email": email, "otp": "000000",
                "password": "newpassword123",
            }),
            content_type="application/json")
        self.assertEqual(resp.status_code, 400)

    def test_reset_password_with_expired_otp_fails(self):
        """An expired OTP is rejected even though it matches."""
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
                {"email": email, "otp": otp, "password": "newpassword123"}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 400)

    def test_reset_password_otp_cannot_be_reused(self):
        """An OTP already consumed is rejected on a second attempt."""
        email, _ = self._signed_in_user()
        self.client.post(
            "/api/v1/auth/forgot-password",
            data=json.dumps({"email": email}),
            content_type="application/json")
        otp = self._otp_for(email)
        first = self.client.post(
            "/api/v1/auth/reset-password",
            data=json.dumps(
                {"email": email, "otp": otp, "password": "newpassword123"}),
            content_type="application/json")
        self.assertEqual(first.status_code, 200)

        second = self.client.post(
            "/api/v1/auth/reset-password",
            data=json.dumps(
                {"email": email, "otp": otp, "password": "anotherpass456"}),
            content_type="application/json")
        self.assertEqual(second.status_code, 400)

    def test_reset_password_rejects_short_new_password(self):
        """The new password still has to meet the minimum length."""
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
        """Repeated wrong-OTP attempts against one account eventually get
        rate-limited — the real defense against a 6-digit code's small
        keyspace, not the code's secrecy alone."""
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
                    "password": "newpassword123",
                }),
                content_type="application/json")
            last_status = resp.status_code
        self.assertEqual(last_status, 429)


if __name__ == "__main__":
    unittest.main()

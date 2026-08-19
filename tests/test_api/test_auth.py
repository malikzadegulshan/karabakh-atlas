#!/usr/bin/python3
"""Tests for the /auth/* views (register, login, logout, me, verify)."""
import json
import unittest
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch
from api.v1.app import app
from api.v1 import auth_utils
from models import storage
from models.user import User

TEST_PASSWORD = "correcthorsebattery"


def _unique_email():
    return "user-{}@example.com".format(uuid.uuid4())


class TestAuthViews(unittest.TestCase):
    """End-to-end tests against the Flask test client."""

    def setUp(self):
        """Create a fresh client and reset the in-memory rate limiter.

        send_email is patched everywhere in this class — no test here
        should depend on actual delivery, just on the token/verification
        logic around it.
        """
        self.client = app.test_client()
        auth_utils.login_limiter._attempts.clear()
        auth_utils.resend_verification_limiter._attempts.clear()
        auth_utils.register_limiter._attempts.clear()
        auth_utils.password_reset_request_limiter._attempts.clear()
        auth_utils.password_reset_attempt_limiter._attempts.clear()
        patcher = patch("api.v1.views.auth.send_email", return_value=True)
        self.mock_send_email = patcher.start()
        self.addCleanup(patcher.stop)

    def _register(self, email=None, password=TEST_PASSWORD):
        email = email or _unique_email()
        resp = self.client.post(
            "/api/v1/auth/register",
            data=json.dumps(
                {"name": "New User", "email": email, "password": password}),
            content_type="application/json")
        return email, resp

    def test_register_creates_account_and_logs_in(self):
        """A successful registration also starts a logged-in session."""
        email, resp = self._register()
        self.assertEqual(resp.status_code, 201)
        body = json.loads(resp.data)
        self.assertEqual(body["email"], email)
        self.assertEqual(body["role"], "user")
        self.assertFalse(body["email_verified"])
        self.assertNotIn("password_hash", body)
        self.assertNotIn("verification_token", body)

        me_resp = self.client.get("/api/v1/auth/me")
        self.assertEqual(me_resp.status_code, 200)
        self.assertEqual(json.loads(me_resp.data)["email"], email)

    def test_register_sends_a_verification_email(self):
        """Registering triggers a verification email to that address."""
        email, resp = self._register()
        self.assertEqual(resp.status_code, 201)
        self.mock_send_email.assert_called_once()
        self.assertEqual(self.mock_send_email.call_args[0][0], email)

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
                 "password": TEST_PASSWORD}),
            content_type="application/json")
        self.assertEqual(first.status_code, 201)

        second = self.client.post(
            "/api/v1/auth/register",
            data=json.dumps(
                {"name": "Second", "email": email,
                 "password": TEST_PASSWORD}),
            content_type="application/json")
        self.assertEqual(second.status_code, 409)

    def test_login_with_correct_credentials(self):
        """Logging in with the right password succeeds and sets a session."""
        email = _unique_email()
        self.client.post(
            "/api/v1/auth/register",
            data=json.dumps(
                {"name": "New User", "email": email,
                 "password": TEST_PASSWORD}),
            content_type="application/json")
        self.client.post("/api/v1/auth/logout")

        resp = self.client.post(
            "/api/v1/auth/login",
            data=json.dumps({"email": email, "password": TEST_PASSWORD}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 200)

    def test_login_with_wrong_password_fails(self):
        """A wrong password is rejected with 401."""
        email = _unique_email()
        self.client.post(
            "/api/v1/auth/register",
            data=json.dumps(
                {"name": "New User", "email": email,
                 "password": TEST_PASSWORD}),
            content_type="application/json")
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
        self.client.post(
            "/api/v1/auth/register",
            data=json.dumps(
                {"name": "New User", "email": email,
                 "password": TEST_PASSWORD}),
            content_type="application/json")
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
        self.client.post(
            "/api/v1/auth/register",
            data=json.dumps(
                {"name": "New User", "email": email,
                 "password": TEST_PASSWORD}),
            content_type="application/json")
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
        rate-limited — this endpoint sends a real email on every call,
        so it's also a spam-relay vector without a cap."""
        last_status = None
        for _ in range(auth_utils.register_limiter.max_attempts + 1):
            _, resp = self._register()
            last_status = resp.status_code
        self.assertEqual(last_status, 429)

    def _token_for(self, email):
        for user in storage.all(User).values():
            if user.email == email:
                return user.verification_token
        raise AssertionError("no user found for {}".format(email))

    def test_verify_with_correct_token_succeeds(self):
        """The token from the verification email marks the account verified."""
        email, _ = self._register()
        token = self._token_for(email)
        resp = self.client.post(
            "/api/v1/auth/verify",
            data=json.dumps({"token": token}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(json.loads(resp.data)["email_verified"])

    def test_verify_with_wrong_token_fails(self):
        """A token that doesn't match any user is rejected."""
        self._register()
        resp = self.client.post(
            "/api/v1/auth/verify",
            data=json.dumps({"token": "not-a-real-token"}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 400)

    def test_verify_with_expired_token_fails(self):
        """An expired token is rejected even though it matches."""
        email, _ = self._register()
        for user in storage.all(User).values():
            if user.email == email:
                user.verification_token_expires_at = (
                    datetime.utcnow() - timedelta(seconds=1))
                user.save()
                break
        token = self._token_for(email)
        resp = self.client.post(
            "/api/v1/auth/verify",
            data=json.dumps({"token": token}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 400)

    def test_verify_token_cannot_be_reused(self):
        """A token already consumed is rejected on a second attempt."""
        email, _ = self._register()
        token = self._token_for(email)
        first = self.client.post(
            "/api/v1/auth/verify",
            data=json.dumps({"token": token}),
            content_type="application/json")
        self.assertEqual(first.status_code, 200)

        second = self.client.post(
            "/api/v1/auth/verify",
            data=json.dumps({"token": token}),
            content_type="application/json")
        self.assertEqual(second.status_code, 400)

    def test_resend_verification_requires_login(self):
        """Resending needs a logged-in session."""
        anon_client = app.test_client()
        resp = anon_client.post("/api/v1/auth/resend-verification")
        self.assertEqual(resp.status_code, 401)

    def test_resend_verification_sends_another_email(self):
        """Resending triggers a second verification email."""
        self._register()
        self.mock_send_email.reset_mock()
        resp = self.client.post("/api/v1/auth/resend-verification")
        self.assertEqual(resp.status_code, 200)
        self.mock_send_email.assert_called_once()

    def test_resend_verification_rejected_once_already_verified(self):
        """A verified account can't request another verification email."""
        email, _ = self._register()
        token = self._token_for(email)
        self.client.post(
            "/api/v1/auth/verify",
            data=json.dumps({"token": token}),
            content_type="application/json")

        resp = self.client.post("/api/v1/auth/resend-verification")
        self.assertEqual(resp.status_code, 400)

    def test_resend_verification_rate_limited(self):
        """Repeated resend requests eventually get rate-limited."""
        self._register()
        last_status = None
        limit = auth_utils.resend_verification_limiter.max_attempts
        for _ in range(limit + 1):
            resp = self.client.post("/api/v1/auth/resend-verification")
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
        email, _ = self._register()
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
        email, _ = self._register()
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
        email, _ = self._register()
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
        email, _ = self._register()
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
        email, _ = self._register()
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
        email, _ = self._register()
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
        email, _ = self._register()
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
        email, _ = self._register()
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
        email, _ = self._register()
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

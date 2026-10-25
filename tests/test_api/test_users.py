#!/usr/bin/python3
"""Tests for the admin-only account approval views (/users/*)."""
import json
import unittest
import uuid
from api.v1.app import app
from api.v1 import auth_utils
from models import storage
from models.user import User
from tests.test_api.helpers import register_and_login

PASSWORD = "correcthorsebattery"


def _email():
    return "user-{}@example.com".format(uuid.uuid4())


class TestUserApproval(unittest.TestCase):
    """Listing, approving, and rejecting pending accounts."""

    def setUp(self):
        auth_utils.login_limiter._attempts.clear()
        auth_utils.register_limiter._attempts.clear()

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
        """Reject only ever touches pending accounts, never members or
        admins."""
        regular = app.test_client()
        register_and_login(regular, "Member", _email(), PASSWORD)
        member = [u for u in storage.all(User).values()
                  if u.name == "Member"][0]
        resp = self.admin.delete(
            "/api/v1/users/{}/reject".format(member.id))
        self.assertEqual(resp.status_code, 404)
        self.assertIn("User.{}".format(member.id), storage.all(User))


if __name__ == "__main__":
    unittest.main()

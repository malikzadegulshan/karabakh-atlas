#!/usr/bin/python3
"""Shared helpers for the API tests."""
import json
from models.user import User


def register_and_login(client, name, email, password):
    """Give `client` a signed-in, approved regular user.

    Registering through the API now only files a request that an admin
    has to approve, so tests that just need a logged-in user create an
    already-approved one directly and sign in. Returns the login
    response (the same JSON shape the old register response had).
    """
    user = User(
        name=name, email=email, role="user", approved=True,
        email_verified=False)
    user.set_password(password)
    user.save()
    return client.post(
        "/api/v1/auth/login",
        data=json.dumps({"email": email, "password": password}),
        content_type="application/json")

# Karabakh Atlas - Dirchalish

Karabakh Atlas is a map website project for exploring Karabakh and its
cities through an interactive, visual interface. It's split into a
backend (a REST API serving region/city data) and a frontend (a
Leaflet-based map UI that renders that data).

## License

All rights reserved — see [LICENSE](LICENSE).

## Running locally

**Backend:**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 seed_data.py
python3 -m api.v1.app
```

By default this uses a local JSON file for storage — no database setup
needed. See [Environment variables](#environment-variables) below to run
against PostgreSQL instead.

**Frontend** (in a second terminal):

```bash
cd frontend
python3 -m http.server 8000
```

Then open `http://localhost:8000` in a browser. The API listens on
`http://localhost:5000` by default.

## Accounts

Regions/cities can only be created, edited, or deleted by a logged-in
admin — anyone can create a regular account from the "Sign in" button,
but that gets the "user" role, which is read-only. To get the first
admin account, set `KBA_ADMIN_EMAIL` and `KBA_ADMIN_PASSWORD` (and
optionally `KBA_ADMIN_NAME`) before starting the backend — it creates
that admin on boot if it doesn't already exist yet:

```bash
export KBA_ADMIN_EMAIL=you@example.com KBA_ADMIN_PASSWORD='choose-a-real-password'
python3 -m api.v1.app
```

Sign in with those credentials from the site, and the "Manage" button
appears. Further admins can then be promoted directly in the database,
or by re-running with different `KBA_ADMIN_*` values for a second admin.

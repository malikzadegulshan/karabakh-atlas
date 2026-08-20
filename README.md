# Karabakh Atlas - Dirchalish

Karabakh Atlas is an interactive map for exploring Karabakh — its
regions, cities, points of interest, and history — through a
Leaflet-based visual interface backed by a REST API.

## Features

- **Interactive map** — regions, cities, and 20+ categories of points
  of interest (cafes, museums, landmarks, roads, ...), each with its
  own icon, rendered at the zoom level where they're actually useful.
- **Historical imagery timeline** — a year slider (2014–present)
  swaps in NASA GIBS MODIS satellite imagery for that year, alongside
  historical events pinned to the map.
- **Place details** — name, description, and photo (routed through a
  resize/compress proxy so a full-resolution admin-supplied image
  doesn't get downloaded at full size), phone/website for points of
  interest, live weather for cities.
- **Search** — a live results dropdown across every place as you type.
- **Distance measurement** — pick a second place from a detail view
  and see the real (haversine) distance, drawn as a line on the map.
- **Shareable permalinks** — opening a place updates the URL
  (`?place=<id>`), so a copied/bookmarked link reopens the same place.
- **Accounts** — register/login, email verification, forgotten-password
  reset via a time-limited OTP, all with rate limiting.
- **Favorites** — signed-in users can save places and find them again
  from the account menu.
- **Community forum** — visitors can share opinions about Karabakh in
  general or a specific place; every post is held for admin moderation
  before it's public.
- **Admin panel** — CRUD for regions/cities/points of interest and
  timeline events, plus the forum moderation queue, gated by an admin
  role on the account.
- **"About this atlas" dashboard** — a public, unauthenticated
  snapshot of what's in the atlas (counts by category, historical
  events, approved opinions).
- **Installable / offline-capable** — a web app manifest and service
  worker cache the app shell, so the UI still loads without a network
  connection (only live data like weather/API calls need one).
- **Accessibility** — keyboard-operable custom widgets (modal focus
  trapping, a keyboard-resizable bottom sheet on mobile), a skip link,
  and labels on every form field, not just placeholder text.
- **Four languages** — English, Azərbaycanca, Türkçe, and Русский.
- **Light/dark mode**, following the system preference or a manual
  toggle.

## Architecture

```
frontend/  (static HTML/CSS/vanilla JS — no build step)
   |
   |  fetch() over HTTPS, cookie-based sessions
   v
api/v1/  (Flask REST API)
   |
   v
models/  (SQLAlchemy models, storage-engine-agnostic)
   |
   +-- FileStorage  (JSON file — zero setup, used for local dev/tests)
   +-- DBStorage    (PostgreSQL — used in production)
```

- **Backend**: Flask + SQLAlchemy, documented with an OpenAPI spec
  served through Swagger UI at `/api/docs`. Every model
  (`models/*.py`) works against either storage engine unchanged —
  the engine is selected once via `KBA_TYPE_STORAGE`
  (`file` or `db`), and the rest of the codebase never checks which
  one is active.
- **Frontend**: plain HTML/CSS/JS, no framework or build step — each
  feature area is its own file (`app.js` for the map/search/distance/
  permalinks, `auth.js`, `admin.js`, `forum.js`, `favorites.js`,
  `stats.js`), sharing a handful of globals (`t()` for translations,
  `apiRequest()` for authenticated calls, `currentUser`, ...) loaded
  in order from `index.html`.
- **Auth**: server-side sessions via a signed cookie
  (`KBA_SECRET_KEY`), not tokens — `credentials: "include"` on every
  frontend request. Passwords are hashed, never stored or logged in
  plain text; the reset-password flow uses a 6-digit OTP with a
  15-minute expiry and its own rate limiter, separate from the general
  request rate limiter.
- **Email**: transactional email (verification links, reset codes)
  goes through the Resend HTTP API rather than SMTP — see
  `api/v1/mailer.py` for why. Unconfigured (`RESEND_API_KEY` unset),
  it just logs the message instead of sending it, so registration/
  verification/reset are fully testable in local dev without a real
  account.

## Tech stack

| Layer | Choice |
|---|---|
| Backend | Flask 3, SQLAlchemy 2 |
| Database | PostgreSQL (production) / JSON file (local dev, tests) |
| Frontend | Vanilla JS, [Leaflet](https://leafletjs.com/) for the map |
| Auth | Server-side sessions, cookie-based |
| Email | [Resend](https://resend.com) HTTP API |
| Deployment | [Render](https://render.com) (see `render.yaml`) |
| CI | GitHub Actions — full test suite against a real Postgres service |

## Project structure

```
api/v1/            Flask app, views (one file per resource), auth
                    helpers, request validation, OpenAPI spec
models/             SQLAlchemy models + the two storage engines
frontend/           Static site — no build step, served as-is
tests/              Unit tests (models) and API tests (Flask test
                    client), run against both storage engines
seed_data.py        Idempotent starter regions/cities for a fresh DB
render.yaml         Render Blueprint — backend, frontend, and a free
                    Postgres instance, deployed together
```

## Running locally

```bash
pip install -r requirements.txt
export KBA_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
python3 -m api.v1.app  # backend on :5000 (KBA_TYPE_STORAGE=file by
                        # default — no database needed)

cd frontend && python3 -m http.server 8000  # frontend on :8000
```

`.env.example` documents every other variable this app reads
(`os.environ.get(...)` throughout — there's no `.env`-loading library
in the mix, so it's a reference to export from, not a file to drop in
as-is). Everything besides `KBA_SECRET_KEY` — PostgreSQL connection,
admin bootstrap, the email provider — is optional for local dev and
has a safe fallback.

## Testing

```bash
python3 -m pycodestyle api/ models/ tests/    # lint
KBA_TYPE_STORAGE=file python3 -m unittest discover -s tests

# Against Postgres too — KBA_DB_* vars as in .env.example (or
# DATABASE_URL); KBA_ENV=test drops and recreates tables each run.
KBA_TYPE_STORAGE=db KBA_ENV=test KBA_DB_USER=... KBA_DB_PWD=... \
  KBA_DB_HOST=localhost KBA_DB_NAME=... python3 -m unittest discover -s tests
```

CI (`.github/workflows/tests.yml`) runs the full suite against a real
Postgres service on every push, so both storage engines stay honest.

## Deployment

`render.yaml` defines three services deployed together from the
Render dashboard (New → Blueprint): the API, the static frontend, and
a free PostgreSQL database. Secrets (admin bootstrap, session key,
email API key) are filled in through Render's dashboard, never
committed.

## API docs

The full OpenAPI spec is served as an interactive Swagger UI at
`/api/docs` on the running backend (locally: `http://localhost:5000/api/docs`).

## License

All rights reserved — see [LICENSE](LICENSE).

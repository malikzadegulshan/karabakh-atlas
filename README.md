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
- **Place details** — name, description, photo, phone/website for
  points of interest, live weather for cities.
- **Search** — a live results dropdown across every place as you type.
- **Distance measurement** — pick a second place from a detail view
  and see the real distance, drawn as a line on the map.
- **Shareable permalinks** — opening a place updates the URL, so a
  copied/bookmarked link reopens the same place.
- **Accounts** — register/login with email verification and
  password reset.
- **Favorites** — signed-in users can save places and find them again
  from the account menu.
- **Community forum** — visitors can share opinions about Karabakh in
  general or a specific place; every post is held for admin moderation
  before it's public.
- **Admin panel** — CRUD for regions/cities/points of interest and
  timeline events, plus the forum moderation queue.
- **"About this atlas" dashboard** — a public snapshot of what's in
  the atlas (counts by category, historical events, approved opinions).
- **Installable / offline-capable** — a web app manifest and service
  worker cache the app shell, so the UI still loads without a network
  connection.
- **Accessibility** — keyboard-operable custom widgets, a skip link,
  and labels on every form field.
- **Four languages** — English, Azərbaycanca, Türkçe, and Русский.
- **Light/dark mode**, following the system preference or a manual
  toggle.

## Tech stack

| Layer | Choice |
|---|---|
| Backend | Flask, SQLAlchemy |
| Database | PostgreSQL (production) / JSON file (local dev, tests) |
| Frontend | Vanilla JS, [Leaflet](https://leafletjs.com/) for the map |
| Deployment | [Render](https://render.com) |
| CI | GitHub Actions |

## Project structure

```
api/v1/            Flask app, views, request validation
models/             Data models + storage engines
frontend/           Static site — no build step, served as-is
tests/              Test suite
```

## Running locally

See `.env.example` for the environment variables needed and their
defaults. At minimum:

```bash
pip install -r requirements.txt
python3 -m api.v1.app  # backend on :5000

cd frontend && python3 -m http.server 8000  # frontend on :8000
```

## Testing

```bash
python3 -m pycodestyle api/ models/ tests/    # lint
python3 -m unittest discover -s tests
```

CI runs the full suite on every push.

## Contributing

Pull requests are welcome. Please don't commit secrets or `.env`
files — configuration is documented in `.env.example` only.

Found a security issue? See [SECURITY.md](.github/SECURITY.md) —
please don't open a public issue for it.

## License

All rights reserved — see [LICENSE](LICENSE).

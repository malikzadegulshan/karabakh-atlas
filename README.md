# Karabakh Atlas

Karabakh Atlas is a map website project for exploring Karabakh and its
cities through an interactive, visual interface.

The project is split into two parts:

- **Backend** (this repository, implemented) — a RESTful JSON API that
  stores and serves region/city data.
- **Frontend** (not built yet) — the interactive map UI (e.g. Leaflet or
  Mapbox GL) that calls this API to render regions and city markers.

## Project status

- [x] Backend — data models, storage engine, REST API, tests
- [x] Frontend — MVP demo (map + markers, see below); production frontend still open
- [ ] Content — curated region/city dataset
- [ ] Deployment

Anyone picking up the frontend should point it at `/api/v1/regions` and
`/api/v1/cities`, documented below.

## Data model

- **Region** — `name`, `description`, and the `cities` that belong to it.
- **City** — `name`, `latitude`, `longitude`, `description` (an info
  section shown in the map popup), `alt_names` (alternate name
  spellings/languages), `image_url` + `image_credit` (a picture and its
  attribution, also shown in the popup), and `region_id`.

This repo doesn't ship any photos itself — sourcing and licensing
images for specific real-world places is left to whoever curates the
content, so `image_url` should point at an image you have the right to
use (e.g. your own photo, or one under a permissive license such as
Wikimedia Commons CC-BY/CC0), with `image_credit` holding the
attribution text to display alongside it.


```bash
python3 seed_data.py
```

It's safe to re-run — existing regions/cities are matched by name
rather than duplicated.

---

## Backend

### Project structure

```
karabakh-atlas/
├── console.py                 # interactive shell for managing stored data
├── models/
│   ├── base_model.py           # BaseModel: id, created_at, updated_at
│   ├── region.py                # Region: a named area grouping cities
│   ├── city.py                  # City: a map point (name, lat/lng, description)
│   └── engine/
│       ├── file_storage.py      # default JSON-file persistence (no DB needed)
│       └── db_storage.py        # MySQL persistence via SQLAlchemy
├── api/v1/
│   ├── app.py                   # Flask application entry point
│   └── views/                   # status, regions, cities route handlers
├── tests/                      # unittest suite (models + API)
├── setup_mysql_dev.sql          # creates the local dev MySQL DB/user
├── setup_mysql_test.sql         # creates the local test MySQL DB/user
└── requirements.txt
```

### Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then edit values as needed
```

By default `KBA_TYPE_STORAGE=file`, which persists data to a local
`kba_file.json` file — no database server required. This is the
easiest way to develop and run the test suite.

#### Using MySQL instead

1. Run `mysql -u root -p < setup_mysql_dev.sql` (and
   `setup_mysql_test.sql` for the test database). Change the placeholder
   passwords in those files before using anything beyond local dev.
2. Set `KBA_TYPE_STORAGE=db` in `.env` and fill in the `KBA_MYSQL_*`
   variables to match.
3. Never commit your `.env` file or real database credentials —
   `.env` is already git-ignored.

### Running the API

```bash
source .venv/bin/activate
export $(cat .env | xargs)   # or otherwise load your env vars
python3 -m api.v1.app
```

The API listens on `http://0.0.0.0:5000` by default.

### Endpoints

| Method | Path                          | Description                             |
|--------|-------------------------------|------------------------------------------|
| GET    | `/api/v1/status`              | Health check                             |
| GET    | `/api/v1/stats`               | Object counts                            |
| GET    | `/api/v1/regions`             | List all regions                         |
| POST   | `/api/v1/regions`             | Create a region                          |
| GET    | `/api/v1/regions/<id>`        | Get one region                           |
| PUT    | `/api/v1/regions/<id>`        | Update a region                          |
| DELETE | `/api/v1/regions/<id>`        | Delete a region                          |
| GET    | `/api/v1/regions/<id>/cities` | List cities in a region                  |
| POST   | `/api/v1/regions/<id>/cities` | Create a city in a region                |
| GET    | `/api/v1/cities`              | List all cities (`?q=` filters by name)  |
| GET    | `/api/v1/cities/<id>`         | Get one city                             |
| PUT    | `/api/v1/cities/<id>`         | Update a city                            |
| DELETE | `/api/v1/cities/<id>`         | Delete a city                            |

Example:

```bash
curl -X POST http://localhost:5000/api/v1/regions \
  -H "Content-Type: application/json" \
  -d '{"name": "Sample Region"}'
```

### Protecting the write endpoints before deploying publicly

By default, `POST`/`PUT`/`DELETE` have no authentication — fine for
local dev, but if you deploy this anywhere public, anyone who finds the
URL could create/overwrite/delete your data (and rack up cost on
metered hosting). Set `KBA_API_KEY` in `.env` before deploying, and
every write request must then include a matching header:

```bash
curl -X POST http://localhost:5000/api/v1/regions \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $KBA_API_KEY" \
  -d '{"name": "Sample Region"}'
```

`GET` requests are never affected. Leaving `KBA_API_KEY` unset keeps
the previous open behavior, which is only appropriate for local dev.

### Command-line interpreter

`console.py` supports `create`, `show`, `destroy`, `all`, `count`, and
`update` against `Region` and `City`, e.g.:

```bash
$ python3 console.py
(kba) create Region name="Sample_Region"
d1a5b6c0-...
(kba) all Region
[...]
(kba) quit
```

### Tests

```bash
python3 -m unittest discover tests
```

### Notes on API keys / secrets

This backend does not itself require any third-party API key. If the
frontend uses a map-tile provider that needs one (Mapbox, etc.), keep
that key in the frontend's own environment configuration — never commit
it to this repository.

## Frontend (MVP demo)

`frontend/` is a minimal static page — plain HTML/CSS/JS, no build step
— that renders a Leaflet map, fetches `/api/v1/cities` from the running
backend, and drops a marker + sidebar entry for each city. It's a proof
that the API and a map UI work together end-to-end, not a production
frontend.

Leaflet itself is vendored under `frontend/vendor/leaflet/` (no CDN
dependency); only the map tile images are fetched live — a layer
toggle (top-right) switches between OpenStreetMap streets and Esri
World Imagery satellite tiles, both free and keyless.

The UI has a language switcher — English, Azerbaijani, Turkish, and
Russian — in `frontend/i18n.js`. City data also translates: `City` has
optional `name_i18n`/`description_i18n` JSON fields (e.g.
`{"az": "...", "tr": "...", "ru": "..."}`); the frontend uses the entry
matching the selected language and falls back to the plain
`name`/`description` fields when a translation is missing. All of
these (UI strings and the seeded city translations in
`seed_data.py`) are my own best-effort translations, not reviewed by
native speakers — treat them as a starting point and correct any
phrasing that's off before relying on them publicly.

To run it:

1. Start the backend (see above) — it must be reachable at
   `http://localhost:5000` (or update `frontend/config.js` if not).
2. Add at least one region and city so there's something to see (via
   `console.py` or the API, as shown above).
3. Serve the frontend as static files (opening `index.html` directly
   from disk can trip browser CORS/file restrictions, so use a simple
   server instead):
   ```bash
   cd frontend
   python3 -m http.server 8000
   ```
4. Open `http://localhost:8000` in a browser.

## Roadmap

- [ ] Production frontend (this MVP is intentionally minimal)
- [ ] Agree on and populate the actual region/city dataset
- [ ] Decide on hosting/deployment for both API and frontend
- [ ] Optional: authentication for editing data, image uploads,
      region boundary (GeoJSON) support
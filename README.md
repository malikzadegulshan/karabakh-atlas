# Karabakh Atlas — Backend

Backend API for a map website that lets users explore Karabakh and its
cities. It exposes a RESTful JSON API that a separate frontend (any map
library — Leaflet, Mapbox GL, etc.) can consume to render regions and
city markers.

## Project structure

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

## Data model

- **Region** — `name`, `description`, and the `cities` that belong to it.
- **City** — `name`, `latitude`, `longitude`, `description`, `alt_names`
  (a place for alternate name spellings/languages), and `region_id`.

The seed data is deliberately left empty. Karabakh place names are used
differently by different sources, so this backend does not ship any
opinionated list of cities — populate it yourself via the API or
`console.py` with whatever dataset your project has agreed on.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then edit values as needed
```

By default `KBA_TYPE_STORAGE=file`, which persists data to a local
`kba_file.json` file — no database server required. This is the
easiest way to develop and run the test suite.

### Using MySQL instead

1. Run `mysql -u root -p < setup_mysql_dev.sql` (and
   `setup_mysql_test.sql` for the test database). Change the placeholder
   passwords in those files before using anything beyond local dev.
2. Set `KBA_TYPE_STORAGE=db` in `.env` and fill in the `KBA_MYSQL_*`
   variables to match.
3. Never commit your `.env` file or real database credentials —
   `.env` is already git-ignored.

## Running the API

```bash
source .venv/bin/activate
export $(cat .env | xargs)   # or otherwise load your env vars
python3 -m api.v1.app
```

The API listens on `http://0.0.0.0:5000` by default.

### Endpoints

| Method | Path                            | Description                    |
|--------|----------------------------------|---------------------------------|
| GET    | `/api/v1/status`                 | Health check                    |
| GET    | `/api/v1/stats`                  | Object counts                   |
| GET    | `/api/v1/regions`                | List all regions                |
| POST   | `/api/v1/regions`                | Create a region                 |
| GET    | `/api/v1/regions/<id>`           | Get one region                  |
| PUT    | `/api/v1/regions/<id>`           | Update a region                 |
| DELETE | `/api/v1/regions/<id>`           | Delete a region                 |
| GET    | `/api/v1/regions/<id>/cities`   | List cities in a region         |
| POST   | `/api/v1/regions/<id>/cities`   | Create a city in a region       |
| GET    | `/api/v1/cities`                 | List all cities (`?q=` filters by name) |
| GET    | `/api/v1/cities/<id>`            | Get one city                    |
| PUT    | `/api/v1/cities/<id>`            | Update a city                   |
| DELETE | `/api/v1/cities/<id>`            | Delete a city                   |

Example:

```bash
curl -X POST http://localhost:5000/api/v1/regions \
  -H "Content-Type: application/json" \
  -d '{"name": "Sample Region"}'
```

## Command-line interpreter

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

## Tests

```bash
python3 -m unittest discover tests
```

## Notes on API keys / secrets

This backend does not itself require any third-party API key. If your
frontend uses a map-tile provider that needs one (Mapbox, etc.), keep
that key in the frontend's own environment configuration — never commit
it to this repository.

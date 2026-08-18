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
needed.

**Frontend** (in a second terminal):

```bash
cd frontend
python3 -m http.server 8000
```

Then open `http://localhost:8000` in a browser. The API listens on
`http://localhost:5000` by default.



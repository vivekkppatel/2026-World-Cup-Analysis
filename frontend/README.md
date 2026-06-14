# World Cup 2026 — React Analyzer (frontend)

A single-page React dashboard for the WC 2026 analytics platform. Opens
directly on the analytics (Predictions / Team Stats / Bracket / Info) with a
floating right-side pill nav and crossfade tabs.

**Stack:** React + Vite · Tailwind CSS · Framer Motion · Lucide icons.

## How the pieces fit

```
PostgreSQL  ──►  FastAPI (api/main.py)  ──►  React (this app)
   ▲                                            reads /api/* over HTTP
   │
API-Football / openfootball  ──►  scripts/refresh_live.py  (live scores)
```

The React app reads from the FastAPI backend; if the backend is down it falls
back to baked-in mock data so the UI never breaks. All data shapes live in
[`src/data/api.js`](src/data/api.js).

## Run it locally (three terminals)

```bash
# 1) Backend API (from the repo root, venv active)
python -m uvicorn api.main:app --reload --port 8000

# 2) Frontend (from this folder)
npm install      # first time only
npm run dev      # → http://localhost:5173

# 3) (optional) pull live scores into the DB
python scripts/refresh_live.py
```

Open http://localhost:5173. The dashboard shows the real model output
(France predicted champion, USA out in the semis, the coherent bracket).

## Going live with real match scores

Add an [API-Football](https://www.api-football.com/) key to the repo-root
`.env` (`APIFOOTBALL_KEY=...`), then run `python scripts/refresh_live.py`
(or let `app/utils/live.py` auto-refresh). API-Football is the real-time
source — once matches kick off, scores flow DB → API → dashboard.

## Build for deployment

```bash
npm run build    # → dist/  (static files for Vercel / Netlify / any host)
```

Set `VITE_API_BASE` to your deployed API URL before building so the static
site knows where to fetch from.

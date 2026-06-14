# Deploying the World Cup 2026 Analyzer

Three pieces go live: **PostgreSQL** (data), the **FastAPI backend** (`api/main.py`),
and the **React frontend** (`frontend/`). This guide uses the easiest free path.
Everything that needs an account is marked **[you]** — those steps need your
login (account creation and OAuth can't be automated).

```
React (Vercel/Render static)  ──fetch──►  FastAPI (Render/Railway)  ──►  PostgreSQL (Render/Neon)
```

---

## Step 0 — Push the repo to GitHub **[you]**

Hosts deploy from a Git repo. Create an empty repo on github.com, then:

```bash
git remote add origin https://github.com/<you>/worldcup2026.git
git push -u origin main
```

---

## Step 1 — A cloud PostgreSQL, populated with your data

**Create the database [you]:** the simplest is [Neon](https://neon.tech) (free,
generous) or a Render PostgreSQL (free 90 days). Either gives you a
**connection string** like `postgresql://user:pass@host/db`.

**Populate it — fastest path (copy your local DB up):**

```bash
# 1) dump your local, fully-loaded database
& "C:\Program Files\PostgreSQL\18\bin\pg_dump.exe" -U postgres worldcup2026 -Fc -f wc2026.dump

# 2) restore into the cloud DB (paste your cloud connection string)
& "C:\Program Files\PostgreSQL\18\bin\pg_restore.exe" --no-owner --clean \
    -d "postgresql://user:pass@host/db" wc2026.dump
```

This copies up the teams, matches, predictions, bracket, and all the `v_*`
views in one shot — no re-downloading StatsBomb. *(Alternative: set
`DATABASE_URL` to the cloud string locally and re-run the pipeline from
README step 5–7 — slower, but no pg_dump needed.)*

---

## Step 2 — Deploy the backend API

**Option A — Render Blueprint (one click, recommended):**
On [Render](https://render.com) **[you]**: New → **Blueprint** → connect the
repo. It reads [`render.yaml`](../render.yaml) and creates the API + a Postgres
+ the static frontend together. Then set the secret `APIFOOTBALL_KEY` in the
dashboard. *(If you populated your own Neon DB in Step 1, point the API's
`DATABASE_URL` at it instead of the blueprint's database.)*

**Option B — Railway / Fly / Cloud Run:** they build the [`Dockerfile`](../Dockerfile)
directly. Set two env vars: `DATABASE_URL` (your cloud DB) and `APIFOOTBALL_KEY`.

Verify: open `https://your-api.onrender.com/api/health` → `{"ok":true}`.

> The match-predictor's LogReg blend needs `models/match_predictor.pkl` (a
> gitignored build artifact). Without it the predictor still works (Poisson
> only). To include it, commit the file or run `python scripts/train_model.py`
> against the cloud DB.

---

## Step 3 — Deploy the frontend

**Vercel (recommended for React) [you]:** import the repo, set **Root
Directory = `frontend`**. Add one env var:

```
VITE_API_BASE = https://your-api.onrender.com
```

[`frontend/vercel.json`](../frontend/vercel.json) handles the SPA routing.
Vercel gives you the public URL — that's your live site.

*(Or let the Render Blueprint host the frontend too — it's already in
`render.yaml`.)*

---

## Environment variables, at a glance

| Service | Variable | Value |
|---|---|---|
| Backend | `DATABASE_URL` | cloud Postgres connection string |
| Backend | `APIFOOTBALL_KEY` | your API-Football key (for live scores/form) |
| Frontend | `VITE_API_BASE` | the deployed backend URL (e.g. `https://wc2026-api.onrender.com`) |

## Keeping it live

Once data starts flowing, schedule a daily refresh (cron job, or run locally
against the cloud `DATABASE_URL`):

```bash
python scripts/refresh_live.py     # live scores (API-Football → DB)
python scripts/refresh_form.py     # competition-weighted recent form
python scripts/run_bracket_sim.py  # re-simulate the bracket
```

The deployed dashboard reads the updated DB automatically.

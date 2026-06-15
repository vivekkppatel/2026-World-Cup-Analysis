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

## Step 1 — Supabase PostgreSQL, populated with your data

**Create the database [you]:** at [supabase.com](https://supabase.com) → New
Project. Once it's up: **Project Settings → Database → Connection string →
URI**. It looks like:

```
postgresql://postgres:[YOUR-PASSWORD]@db.<ref>.supabase.co:5432/postgres
```

Supabase requires SSL, so the app appends `?sslmode=require` automatically when
the host contains `supabase`. Use the **direct connection** (port 5432) for the
Render backend.

**Populate it — fastest path (copy your local DB up):** the dump is already
generated (`wc2026.dump`, ~280 KB). Restore it into Supabase with your local
PG18 `pg_restore` (drop `--clean`, add `--no-acl` for Supabase's roles):

```powershell
& "C:\Program Files\PostgreSQL\18\bin\pg_restore.exe" --no-owner --no-acl `
    -d "postgresql://postgres:PWD@db.<ref>.supabase.co:5432/postgres" wc2026.dump
```

This copies up the teams, matches, predictions, bracket, and all the `v_*`
views in one shot — no re-downloading StatsBomb. *(If a cross-version restore
errors, the fallback is to set `DATABASE_URL` to the Supabase URI locally and
re-run the pipeline from README step 5–7.)*

> To re-create the dump later: `python scripts/make_dump.py` (or the pg_dump
> command in that script).

---

## Step 2 — Deploy the backend API on Render

On [Render](https://render.com) **[you]**: New → **Web Service** → connect the
repo → it detects the [`Dockerfile`](../Dockerfile). Set two environment
variables:

| Variable | Value |
|---|---|
| `DATABASE_URL` | your Supabase URI from Step 1 |
| `APIFOOTBALL_KEY` | your API-Football key |

Deploy, then verify: `https://your-api.onrender.com/api/health` → `{"ok":true}`.

> *(The `render.yaml` blueprint is for the all-in-one path; for this
> Supabase + Vercel setup you only need the single web service above.)*

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

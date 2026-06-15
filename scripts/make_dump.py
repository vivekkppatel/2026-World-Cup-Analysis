"""
scripts/make_dump.py
─────────────────────
Create a portable dump of the local PostgreSQL database (wc2026.dump) to
upload to a cloud Postgres (Supabase/Neon/Render). Reads DATABASE_URL from
.env so the password never appears on the command line.

Run:
    python scripts/make_dump.py
Then restore (see docs/DEPLOY.md):
    pg_restore --no-owner --no-acl -d "<cloud connection string>" wc2026.dump
"""
import os
import subprocess
import sys
import urllib.parse
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(str(Path(__file__).parent.parent / ".env"))

# Adjust if your PostgreSQL is installed elsewhere.
PG_DUMP = r"C:\Program Files\PostgreSQL\18\bin\pg_dump.exe"
OUT = "wc2026.dump"


def main() -> None:
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL not set in .env"); sys.exit(1)

    p = urllib.parse.urlparse(url)
    env = dict(os.environ)
    if p.password:
        env["PGPASSWORD"] = urllib.parse.unquote(p.password)  # not echoed

    cmd = [PG_DUMP, "-U", p.username or "postgres", "-h", p.hostname or "localhost",
           "-p", str(p.port or 5432), (p.path or "/worldcup2026").lstrip("/"),
           "-Fc", "-f", OUT]
    r = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if r.returncode != 0:
        print("pg_dump failed:\n", r.stderr[:800]); sys.exit(1)
    print(f"✅ {OUT} created ({os.path.getsize(OUT) / 1024:.0f} KB). "
          "Restore it to your cloud DB per docs/DEPLOY.md.")


if __name__ == "__main__":
    main()

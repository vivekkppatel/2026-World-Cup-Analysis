"""
database/db.py
──────────────
SQLAlchemy engine, session factory, and helper utilities.
All other modules import `get_session` and `engine` from here.
"""
import os
import re
from contextlib import contextmanager
from urllib.parse import urlsplit, urlunsplit

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/worldcup2026")

# A Supabase *direct* connection host looks like db.<project-ref>.supabase.co
_SUPABASE_DIRECT = re.compile(r"^db\.([a-z0-9]+)\.supabase\.co$", re.IGNORECASE)


def _use_supabase_pooler(url: str) -> str:
    """
    Rewrite a Supabase *direct* connection URL to the IPv4 session pooler.

    Supabase direct hosts (db.<ref>.supabase.co) are IPv6-only. Any host
    without IPv6 egress — notably Render's free tier — fails with
    "Network is unreachable". The session pooler is reachable over IPv4, so we
    transparently swap to it: host → <region>.pooler.supabase.com and username
    → postgres.<ref> (the tenant-qualified form the pooler requires). The
    password, port, path and query are preserved verbatim.

    No-op for any non-direct host, so local dev and a URL that already points
    at the pooler are left untouched. Region defaults to this project's
    (aws-1-us-east-1); override with SUPABASE_POOLER_REGION if it ever moves.
    """
    parts = urlsplit(url)
    match = _SUPABASE_DIRECT.match(parts.hostname or "")
    if not match:
        return url
    ref = match.group(1)
    region = os.getenv("SUPABASE_POOLER_REGION", "aws-1-us-east-1")
    pooler_host = f"{region}.pooler.supabase.com"

    # Split the raw netloc so the (percent-encoded) password is preserved as-is.
    userinfo, _, _hostport = parts.netloc.rpartition("@")
    user, sep, pw = userinfo.partition(":")
    if user == "postgres":                      # pooler needs postgres.<ref>
        user = f"postgres.{ref}"
    new_userinfo = f"{user}{sep}{pw}"
    port = f":{parts.port}" if parts.port else ""
    new_netloc = f"{new_userinfo}@{pooler_host}{port}"
    return urlunsplit((parts.scheme, new_netloc, parts.path, parts.query, parts.fragment))


def _require_ssl(url: str) -> str:
    """
    Managed Postgres (Supabase, Neon, Render, …) requires TLS. Append
    sslmode=require for remote hosts that don't already specify it; leave
    localhost alone so local dev keeps working without certs.
    """
    if "sslmode=" in url or "localhost" in url or "127.0.0.1" in url:
        return url
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}sslmode=require"


DATABASE_URL = _require_ssl(_use_supabase_pooler(DATABASE_URL))

# ── Engine ────────────────────────────────────────────────────────────────────
engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,       # recycle stale connections
    echo=False,
)

# ── Session Factory ───────────────────────────────────────────────────────────
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


# ── Context manager for safe session handling ─────────────────────────────────
@contextmanager
def get_session():
    """
    Usage:
        with get_session() as session:
            results = session.execute(text("SELECT 1")).fetchall()
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ── Schema initialization ─────────────────────────────────────────────────────
def init_db():
    """Create all tables from schema.sql if they don't exist."""
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path, "r") as f:
        sql = f.read()
    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()
    print("✅ Database schema initialized.")


def health_check() -> bool:
    """Returns True if the database connection is healthy."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"❌ DB health check failed: {e}")
        return False


if __name__ == "__main__":
    if health_check():
        init_db()

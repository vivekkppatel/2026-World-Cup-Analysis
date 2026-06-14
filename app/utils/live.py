"""
app/utils/live.py
──────────────────
Automatic live-data refresh so the dashboard updates itself — no manual
`python scripts/refresh_live.py` needed.

`ensure_live_data()` re-pulls the openfootball schedule/scores (and official
standings if a football-data.org key is set) at most once per TTL, gated by
st.cache_data. Pages call it at the top; wrap the *display* in
st.fragment(run_every=...) and the page re-queries the freshly-upserted DB on
its own.

Reality check: the free upstream feeds only carry results once matches are
actually played and the maintainers publish them. Until then this refreshes
into an unchanged (0-finished) schedule — the plumbing is live, the source is
just empty. `live_status()` reports exactly that to the UI.
"""
import streamlit as st


@st.cache_data(ttl=300, show_spinner=False)
def ensure_live_data(_bucket: int = 0) -> dict:
    """
    Pull the latest WC 2026 data into Postgres. Returns a small status dict.
    Cached for 5 minutes, so concurrent reruns don't hammer the source.
    """
    status = {"ok": False, "finished": 0, "error": None}
    try:
        from scripts.refresh_live import (
            refresh_from_openfootball, refresh_from_apifootball,
            refresh_from_football_data)
        from database.db import engine
        import pandas as pd

        refresh_from_openfootball()
        refresh_from_apifootball()   # live scores (API-Football, if key set)
        refresh_from_football_data()
        n = pd.read_sql(
            "SELECT COUNT(*) AS n FROM matches "
            "WHERE tournament_label='WC 2026' AND status='FINISHED'", engine)
        status["finished"] = int(n["n"][0])
        status["ok"] = True
    except Exception as e:  # never let a refresh failure break the page
        status["error"] = str(e)
    return status


def live_banner() -> None:
    """Render a compact 'auto-updating' status line with a manual refresh."""
    status = ensure_live_data()
    cols = st.columns([4, 1])
    with cols[0]:
        if not status["ok"]:
            st.caption("⚪ Live feed unavailable right now — showing the latest "
                       "data in the database.")
        elif status["finished"] == 0:
            st.caption("🟡 **Auto-updating every 5 min** · the open data feeds "
                       "(openfootball / football-data.org) have no finished WC 2026 "
                       "matches published yet — results appear here automatically "
                       "the moment they do.")
        else:
            st.caption(f"🟢 **Live** · {status['finished']} of 104 matches in · "
                       "auto-updating every 5 minutes.")
    with cols[1]:
        if st.button("🔄 Refresh now", use_container_width=True):
            ensure_live_data.clear()
            st.rerun()

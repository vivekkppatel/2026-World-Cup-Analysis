"""
app/pages/1_Tournament_Overview.py
────────────────────────────────────
Live group standings, top scorers, and recent match results.
Data source: football-data.org API (cached 5 min via st.cache_data).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import pandas as pd

from data.ingest.football_data_api import FootballDataClient
from data.transform.processors import process_standings, process_scorers, process_matches, build_match_label
from app.utils.charts import standings_bar, top_scorers_bar

st.set_page_config(page_title="Tournament Overview · WC 2026", page_icon="🌍", layout="wide")
st.title("🌍 Tournament Overview")
st.caption("Live data refreshes every 5 minutes · Source: football-data.org")

# ── Cached data fetchers ──────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner="Fetching live standings …")
def load_standings() -> pd.DataFrame:
    client = FootballDataClient()
    return process_standings(client.get_standings())

@st.cache_data(ttl=300, show_spinner="Fetching top scorers …")
def load_scorers() -> pd.DataFrame:
    client = FootballDataClient()
    return process_scorers(client.get_scorers(limit=20))

@st.cache_data(ttl=300, show_spinner="Fetching recent results …")
def load_matches() -> pd.DataFrame:
    client = FootballDataClient()
    return process_matches(client.get_matches())

# ── Load data ─────────────────────────────────────────────────────────────────
try:
    standings_df = load_standings()
    scorers_df   = load_scorers()
    matches_df   = load_matches()
    data_loaded  = True
except Exception as e:
    st.error(f"Could not load live data: {e}")
    st.info("Make sure `FOOTBALL_DATA_API_KEY` is set in your `.env` file.")
    data_loaded = False

if not data_loaded:
    st.stop()

# ── KPI row ───────────────────────────────────────────────────────────────────
finished = matches_df[matches_df["status"] == "FINISHED"]
total_goals = (finished["home_score"].fillna(0) + finished["away_score"].fillna(0)).sum()

k1, k2, k3, k4 = st.columns(4)
k1.metric("Matches Played",  len(finished))
k2.metric("Remaining",       len(matches_df) - len(finished))
k3.metric("Goals Scored",    int(total_goals))
k4.metric("Goals / Match",   f"{total_goals / max(len(finished), 1):.2f}")

st.divider()

# ── Group Standings ───────────────────────────────────────────────────────────
st.subheader("Group Standings")

if not standings_df.empty:
    groups = sorted(standings_df["group_name"].dropna().unique())
    tabs = st.tabs([f"Group {g}" for g in groups])

    for tab, group in zip(tabs, groups):
        with tab:
            gdf = standings_df[standings_df["group_name"] == group].sort_values("points", ascending=False)
            col_chart, col_table = st.columns([1.2, 1])

            with col_chart:
                st.plotly_chart(standings_bar(gdf, group), use_container_width=True)

            with col_table:
                display_cols = ["team_name", "played", "won", "drawn", "lost",
                                "goals_for", "goals_against", "points"]
                display_cols = [c for c in display_cols if c in gdf.columns]
                st.dataframe(
                    gdf[display_cols].rename(columns={
                        "team_name": "Team", "played": "P", "won": "W",
                        "drawn": "D", "lost": "L", "goals_for": "GF",
                        "goals_against": "GA", "points": "Pts"
                    }),
                    hide_index=True,
                    use_container_width=True,
                )
else:
    st.info("Standings will populate once group stage matches begin.")

st.divider()

# ── Top Scorers + Recent Results ──────────────────────────────────────────────
col_scorers, col_results = st.columns([1, 1])

with col_scorers:
    st.subheader("⚽ Top Scorers")
    if not scorers_df.empty:
        st.plotly_chart(top_scorers_bar(scorers_df, n=10), use_container_width=True)
    else:
        st.info("Scorer data will populate once matches begin.")

with col_results:
    st.subheader("📋 Recent Results")
    recent = (
        matches_df[matches_df["status"] == "FINISHED"]
        .sort_values("kickoff_utc", ascending=False)
        .head(8)
    )
    if not recent.empty:
        for _, m in recent.iterrows():
            label = build_match_label(
                m.get("home_team_name", "Home"),
                m.get("away_team_name", "Away"),
                m.get("home_score"),
                m.get("away_score"),
            )
            stage = m.get("stage", "").replace("_", " ").title()
            st.markdown(f"**{label}** · *{stage}*")
    else:
        st.info("Results will appear here once matches are played.")

st.divider()

# ── Upcoming Fixtures ─────────────────────────────────────────────────────────
st.subheader("📅 Upcoming Fixtures")
upcoming = (
    matches_df[matches_df["status"].isin(["SCHEDULED", "TIMED"])]
    .sort_values("kickoff_utc")
    .head(10)
)
if not upcoming.empty:
    upcoming_display = upcoming[[
        "kickoff_utc", "stage", "group_name",
        "home_team_api_id", "away_team_api_id"
    ]].copy()
    upcoming_display["kickoff_utc"] = pd.to_datetime(upcoming_display["kickoff_utc"]).dt.strftime("%b %d %H:%M UTC")
    st.dataframe(upcoming_display, hide_index=True, use_container_width=True)
else:
    st.info("No upcoming fixtures found.")

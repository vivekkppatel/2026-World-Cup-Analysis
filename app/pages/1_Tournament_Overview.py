"""
app/pages/1_Tournament_Overview.py
────────────────────────────────────
WC 2026 group standings, top scorers, results and fixtures.

Reads entirely from the PostgreSQL BI views (v_group_standings,
v_top_scorers, v_match_results, v_upcoming_fixtures) — the same views
Tableau/Power BI consume. Standings are computed live from match results,
so the page fills in as scripts/refresh_live.py pulls scores. No API key
needed: the schedule and teams come from the database.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
import streamlit as st

from app.utils.charts import standings_bar, top_scorers_bar
from app.utils.theme import inject_theme
from database.db import engine

st.set_page_config(page_title="Tournament Overview · WC 2026", page_icon="🌍", layout="wide")
inject_theme()
st.title("🌍 Tournament Overview")
st.caption("Group stage standings, scorers & fixtures · computed from the database")

TOURNAMENT = "WC 2026"


# ── Cached loaders (DB views) ─────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner="Loading standings …")
def load_standings() -> pd.DataFrame:
    df = pd.read_sql("SELECT * FROM v_group_standings ORDER BY group_name, position", engine)
    return df.rename(columns={"team": "team_name"})


@st.cache_data(ttl=300, show_spinner="Loading scorers …")
def load_scorers() -> pd.DataFrame:
    df = pd.read_sql(
        "SELECT player, team, goals, assists FROM v_top_scorers "
        "WHERE tournament_label = %(t)s ORDER BY goals DESC, assists DESC LIMIT 20",
        engine, params={"t": TOURNAMENT})
    return df.rename(columns={"player": "player_name", "team": "team_name"})


@st.cache_data(ttl=60, show_spinner="Loading matches …")
def load_results() -> pd.DataFrame:
    return pd.read_sql(
        "SELECT fifa_match_num, kickoff_utc, stage, home_team, away_team, "
        "home_score, away_score FROM v_match_results "
        "WHERE tournament_label = %(t)s ORDER BY kickoff_utc DESC",
        engine, params={"t": TOURNAMENT})


@st.cache_data(ttl=60, show_spinner="Loading fixtures …")
def load_fixtures() -> pd.DataFrame:
    return pd.read_sql(
        "SELECT fifa_match_num, kickoff_utc, stage, group_name, home_team, "
        "away_team, venue, status FROM v_upcoming_fixtures", engine)


standings_df = load_standings()
scorers_df = load_scorers()
results_df = load_results()
fixtures_df = load_fixtures()

# ── KPI row ───────────────────────────────────────────────────────────────────
n_played = len(results_df)
n_total = n_played + len(fixtures_df)
goals = int((results_df["home_score"].fillna(0) + results_df["away_score"].fillna(0)).sum())

k1, k2, k3, k4 = st.columns(4)
k1.metric("Matches Played", n_played)
k2.metric("Remaining", n_total - n_played)
k3.metric("Goals Scored", goals)
k4.metric("Goals / Match", f"{goals / max(n_played, 1):.2f}")

if n_played == 0:
    st.info("⚽ The tournament starts soon — standings and results fill in live as "
            "matches finish. Run `python scripts/refresh_live.py` to pull the latest.")

st.divider()

# ── Group standings ───────────────────────────────────────────────────────────
st.subheader("Group Standings")
if not standings_df.empty:
    groups = sorted(standings_df["group_name"].dropna().unique())
    for row in [groups[i:i + 4] for i in range(0, len(groups), 4)]:
        tabs = st.tabs([f"Group {g}" for g in row])
        for tab, group in zip(tabs, row):
            with tab:
                gdf = standings_df[standings_df["group_name"] == group]
                c_chart, c_table = st.columns([1.2, 1])
                with c_chart:
                    st.plotly_chart(standings_bar(gdf, group), use_container_width=True)
                with c_table:
                    cols = ["team_name", "played", "won", "drawn", "lost",
                            "goals_for", "goals_against", "points"]
                    st.dataframe(
                        gdf[cols].rename(columns={
                            "team_name": "Team", "played": "P", "won": "W",
                            "drawn": "D", "lost": "L", "goals_for": "GF",
                            "goals_against": "GA", "points": "Pts"}),
                        hide_index=True, use_container_width=True)
else:
    st.info("Standings will populate once teams are seeded.")

st.divider()

# ── Top scorers + recent results ──────────────────────────────────────────────
c_scorers, c_results = st.columns(2)
with c_scorers:
    st.subheader("⚽ Top Scorers")
    if not scorers_df.empty:
        st.plotly_chart(top_scorers_bar(scorers_df, n=10), use_container_width=True)
    else:
        st.info("Scorer leaderboard fills in once goals are scored.")

with c_results:
    st.subheader("📋 Recent Results")
    if not results_df.empty:
        for _, m in results_df.head(8).iterrows():
            hs, as_ = int(m["home_score"]), int(m["away_score"])
            stage = str(m["stage"]).replace("_", " ").title()
            st.markdown(f"**{m['home_team']} {hs}–{as_} {m['away_team']}** · *{stage}*")
    else:
        st.info("Results appear here as matches finish.")

st.divider()

# ── Upcoming fixtures ─────────────────────────────────────────────────────────
st.subheader("📅 Upcoming Fixtures")
if not fixtures_df.empty:
    disp = fixtures_df.head(12).copy()
    disp["Kickoff"] = pd.to_datetime(disp["kickoff_utc"]).dt.strftime("%b %d · %H:%M UTC")
    disp["Match"] = disp["home_team"] + " vs " + disp["away_team"]
    disp["Stage"] = disp["stage"].str.replace("_", " ").str.title()
    st.dataframe(
        disp[["Kickoff", "Match", "Stage", "group_name", "venue"]].rename(
            columns={"group_name": "Grp", "venue": "Venue"}),
        hide_index=True, use_container_width=True)
else:
    st.info("No upcoming fixtures found.")

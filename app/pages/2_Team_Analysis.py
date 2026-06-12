"""
app/pages/2_Team_Analysis.py
──────────────────────────────
Deep dive into any team across six tournaments: xG timeline, passing and
pressing volume, and a head-to-head comparison.

Reads from the v_team_match_stats BI view (PostgreSQL) — no slow StatsBomb
cold-download, and the tournament list is whatever event-level data the
database holds.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from app.utils.theme import inject_theme
from database.db import engine

st.set_page_config(page_title="Team Analysis · WC 2026", page_icon="🔵", layout="wide")
inject_theme()
st.title("🔵 Team Analysis")
st.caption("Event-level team performance across WC, Euro, Copa & AFCON tournaments")

BG, TEXT, PRIMARY, GREY, GOLD, RED = "#0F0F23", "#FAFAFA", "#00A86B", "#8B8FA8", "#E8C547", "#E74C3C"
RESULT_COLORS = {"W": PRIMARY, "D": GREY, "L": RED}


# ── Loaders ───────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner="Loading tournaments …")
def load_tournaments() -> list[str]:
    df = pd.read_sql(
        "SELECT tournament_label, MIN(kickoff_utc) k FROM v_team_match_stats "
        "GROUP BY tournament_label ORDER BY k DESC", engine)
    return df["tournament_label"].tolist()


@st.cache_data(ttl=3600, show_spinner="Loading team data …")
def load_team_stats(tournament: str) -> pd.DataFrame:
    df = pd.read_sql(
        "SELECT kickoff_utc, stage, team, opponent, goals_scored, goals_conceded, "
        "team_xg AS xg, shots, passes, pressures FROM v_team_match_stats "
        "WHERE tournament_label = %(t)s ORDER BY kickoff_utc",
        engine, params={"t": tournament})
    df["goals_for"] = df["goals_scored"]
    df["result"] = df.apply(
        lambda r: "W" if r["goals_scored"] > r["goals_conceded"]
        else ("D" if r["goals_scored"] == r["goals_conceded"] else "L"), axis=1)
    return df


tournaments = load_tournaments()
if not tournaments:
    st.warning("No team data loaded. Run `python scripts/load_statsbomb_history.py`.")
    st.stop()

tournament = st.sidebar.selectbox("Tournament", tournaments,
                                  index=tournaments.index("WC 2022") if "WC 2022" in tournaments else 0)
team_stats = load_team_stats(tournament)
teams = sorted(team_stats["team"].unique())
selected_team = st.sidebar.selectbox("Select Team", teams)

team_df = team_stats[team_stats["team"] == selected_team].reset_index(drop=True)
team_df["match_num"] = range(1, len(team_df) + 1)
team_df["result_color"] = team_df["result"].map(RESULT_COLORS)

# ── KPI summary ───────────────────────────────────────────────────────────────
st.subheader(f"📊 {selected_team} — {tournament}")
wins = int((team_df["result"] == "W").sum())
draws = int((team_df["result"] == "D").sum())
losses = int((team_df["result"] == "L").sum())
avg_xg = team_df["xg"].mean()
avg_shots = team_df["shots"].mean()

k = st.columns(6)
k[0].metric("Played", len(team_df))
k[1].metric("W / D / L", f"{wins}/{draws}/{losses}")
k[2].metric("Goals", int(team_df["goals_for"].sum()))
k[3].metric("Avg xG", f"{avg_xg:.2f}")
k[4].metric("Avg Shots", f"{avg_shots:.1f}")
k[5].metric("xG / Shot", f"{avg_xg / max(avg_shots, 1):.3f}")

st.divider()

# ── xG timeline ───────────────────────────────────────────────────────────────
st.subheader("📈 xG by Match")
fig_xg = go.Figure()
fig_xg.add_trace(go.Bar(
    x=team_df["match_num"], y=team_df["xg"], name="xG",
    marker_color=team_df["result_color"],
    hovertemplate="Match %{x}<br>xG: %{y:.2f}<br>Goals: %{customdata}<extra></extra>",
    customdata=team_df["goals_for"]))
fig_xg.add_trace(go.Scatter(
    x=team_df["match_num"], y=team_df["goals_for"], mode="markers", name="Actual Goals",
    marker=dict(color=GOLD, size=10, symbol="star"),
    hovertemplate="Goals: %{y}<extra></extra>"))
if team_df["xg"].notna().any():
    fig_xg.add_hline(y=team_df["xg"].mean(), line_dash="dash", line_color=GREY,
                     annotation_text=f"Avg xG: {team_df['xg'].mean():.2f}")
fig_xg.update_layout(xaxis_title="Match Number", yaxis_title="xG / Goals",
                     plot_bgcolor=BG, paper_bgcolor=BG, font_color=TEXT,
                     legend=dict(orientation="h"), height=320,
                     margin=dict(l=10, r=10, t=10, b=40))
st.plotly_chart(fig_xg, use_container_width=True)

st.divider()

# ── Passing & pressing ────────────────────────────────────────────────────────
c_pass, c_press = st.columns(2)
with c_pass:
    st.subheader("🎯 Passing Volume")
    fig = px.bar(team_df, x="match_num", y="passes", color="result",
                 color_discrete_map=RESULT_COLORS,
                 labels={"passes": "Total Passes", "match_num": "Match"})
    fig.update_layout(plot_bgcolor=BG, paper_bgcolor=BG, font_color=TEXT,
                      height=280, margin=dict(l=10, r=10, t=10, b=30))
    st.plotly_chart(fig, use_container_width=True)
with c_press:
    st.subheader("⚡ Press Intensity")
    fig = px.bar(team_df, x="match_num", y="pressures", color="result",
                 color_discrete_map=RESULT_COLORS,
                 labels={"pressures": "Pressures", "match_num": "Match"})
    fig.update_layout(plot_bgcolor=BG, paper_bgcolor=BG, font_color=TEXT,
                      height=280, margin=dict(l=10, r=10, t=10, b=30))
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── Head-to-head ──────────────────────────────────────────────────────────────
st.subheader("⚔️ Head-to-Head Comparison")
opponent = st.selectbox("Compare against", [t for t in teams if t != selected_team])
opp_df = team_stats[team_stats["team"] == opponent]

metrics = {
    "Avg xG": (team_df["xg"].mean(), opp_df["xg"].mean()),
    "Avg Shots": (team_df["shots"].mean(), opp_df["shots"].mean()),
    "Avg Passes": (team_df["passes"].mean(), opp_df["passes"].mean()),
    "Avg Pressures": (team_df["pressures"].mean(), opp_df["pressures"].mean()),
    "Goals/Match": (team_df["goals_for"].mean(), opp_df["goals_scored"].mean()),
}
comp_df = pd.DataFrame(metrics, index=[selected_team, opponent]).T.round(2)

fig_comp = go.Figure()
fig_comp.add_trace(go.Bar(name=selected_team, x=comp_df[selected_team],
                          y=comp_df.index, orientation="h", marker_color=PRIMARY))
fig_comp.add_trace(go.Bar(name=opponent, x=comp_df[opponent],
                          y=comp_df.index, orientation="h", marker_color=GOLD))
fig_comp.update_layout(barmode="group", plot_bgcolor=BG, paper_bgcolor=BG,
                       font_color=TEXT, height=300, legend=dict(orientation="h"),
                       margin=dict(l=10, r=10, t=10, b=20))
st.plotly_chart(fig_comp, use_container_width=True)

"""
app/pages/2_Team_Analysis.py
──────────────────────────────
Deep dive into any team: xG timeline, passing stats, and form.
Historical data from StatsBomb (WC 2022 proxy until 2026 data builds up).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from data.ingest.statsbomb_loader import StatsBombLoader, COMPETITIONS

st.set_page_config(page_title="Team Analysis · WC 2026", page_icon="🔵", layout="wide")
st.title("🔵 Team Analysis")
st.caption("Historical data from StatsBomb WC 2018 & 2022 · WC 2026 data populates live")

BG, TEXT, PRIMARY, GREY = "#0F0F23", "#FAFAFA", "#00A86B", "#8B8FA8"

# ── Data loading ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner="Loading StatsBomb tournament data …")
def load_team_stats(competition_id: int, season_id: int) -> pd.DataFrame:
    return StatsBombLoader.get_team_match_stats(competition_id, season_id)

# Tournament selector
tournament = st.sidebar.selectbox(
    "Tournament",
    options=["WC 2022", "WC 2018"],
    index=0,
)
comp_key = "wc_2022" if "2022" in tournament else "wc_2018"
comp = COMPETITIONS[comp_key]

try:
    team_stats = load_team_stats(comp["competition_id"], comp["season_id"])
    data_loaded = not team_stats.empty
except Exception as e:
    st.error(f"Could not load StatsBomb data: {e}")
    data_loaded = False

if not data_loaded:
    st.warning("StatsBomb data unavailable. Run `pip install statsbombpy` and ensure internet access.")
    st.stop()

# ── Team selector ─────────────────────────────────────────────────────────────
teams = sorted(team_stats["team"].unique())
selected_team = st.sidebar.selectbox("Select Team", teams)

team_df = team_stats[team_stats["team"] == selected_team].copy()

# ── KPI Summary ───────────────────────────────────────────────────────────────
st.subheader(f"📊 {selected_team} — Tournament Summary")

wins  = (team_df["result"] == "W").sum()
draws = (team_df["result"] == "D").sum()
losses = (team_df["result"] == "L").sum()
avg_xg = team_df["xg"].mean()
avg_shots = team_df["shots"].mean()
total_goals = team_df["goals_for"].sum()

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Played",       len(team_df))
k2.metric("W / D / L",    f"{wins}/{draws}/{losses}")
k3.metric("Goals",        int(total_goals))
k4.metric("Avg xG",       f"{avg_xg:.2f}")
k5.metric("Avg Shots",    f"{avg_shots:.1f}")
k6.metric("xG / Shot",    f"{avg_xg / max(avg_shots, 1):.3f}")

st.divider()

# ── xG per match timeline ─────────────────────────────────────────────────────
st.subheader("📈 xG by Match")

team_df = team_df.reset_index(drop=True)
team_df["match_num"] = range(1, len(team_df) + 1)
team_df["result_color"] = team_df["result"].map({"W": PRIMARY, "D": GREY, "L": "#E74C3C"})

fig_xg = go.Figure()
fig_xg.add_trace(go.Bar(
    x=team_df["match_num"],
    y=team_df["xg"],
    name="xG",
    marker_color=team_df["result_color"],
    hovertemplate="Match %{x}<br>xG: %{y:.2f}<br>Goals: %{customdata}<extra></extra>",
    customdata=team_df["goals_for"],
))
fig_xg.add_trace(go.Scatter(
    x=team_df["match_num"],
    y=team_df["goals_for"],
    mode="markers",
    name="Actual Goals",
    marker=dict(color="#E8C547", size=10, symbol="star"),
    hovertemplate="Goals: %{y}<extra></extra>",
))
fig_xg.add_hline(y=team_df["xg"].mean(), line_dash="dash", line_color=GREY,
                  annotation_text=f"Avg xG: {team_df['xg'].mean():.2f}")
fig_xg.update_layout(
    xaxis_title="Match Number", yaxis_title="xG / Goals",
    plot_bgcolor=BG, paper_bgcolor=BG, font_color=TEXT,
    legend=dict(orientation="h"), height=320,
    margin=dict(l=10, r=10, t=10, b=40),
)
st.plotly_chart(fig_xg, use_container_width=True)

st.divider()

# ── Passing & Pressing stats ───────────────────────────────────────────────────
col_pass, col_press = st.columns(2)

with col_pass:
    st.subheader("🎯 Passing Volume by Match")
    fig_pass = px.bar(
        team_df, x="match_num", y="passes",
        color="result", color_discrete_map={"W": PRIMARY, "D": GREY, "L": "#E74C3C"},
        labels={"passes": "Total Passes", "match_num": "Match"},
    )
    fig_pass.update_layout(plot_bgcolor=BG, paper_bgcolor=BG, font_color=TEXT,
                            height=280, margin=dict(l=10, r=10, t=10, b=30))
    st.plotly_chart(fig_pass, use_container_width=True)

with col_press:
    st.subheader("⚡ Press Intensity by Match")
    fig_press = px.bar(
        team_df, x="match_num", y="pressures",
        color="result", color_discrete_map={"W": PRIMARY, "D": GREY, "L": "#E74C3C"},
        labels={"pressures": "Pressures Applied", "match_num": "Match"},
    )
    fig_press.update_layout(plot_bgcolor=BG, paper_bgcolor=BG, font_color=TEXT,
                             height=280, margin=dict(l=10, r=10, t=10, b=30))
    st.plotly_chart(fig_press, use_container_width=True)

st.divider()

# ── Head-to-head comparison ───────────────────────────────────────────────────
st.subheader("⚔️ Head-to-Head Comparison")
other_teams = [t for t in teams if t != selected_team]
opponent = st.selectbox("Compare against", other_teams)
opp_df = team_stats[team_stats["team"] == opponent]

comparison_metrics = {
    "Avg xG":      (team_df["xg"].mean(),        opp_df["xg"].mean()),
    "Avg Shots":   (team_df["shots"].mean(),      opp_df["shots"].mean()),
    "Avg Passes":  (team_df["passes"].mean(),     opp_df["passes"].mean()),
    "Avg Pressures":(team_df["pressures"].mean(), opp_df["pressures"].mean()),
    "Goals/Match": (team_df["goals_for"].mean(),  opp_df["goals_for"].mean()),
}

comp_df = pd.DataFrame(comparison_metrics, index=[selected_team, opponent]).T
comp_df.columns = [selected_team, opponent]
comp_df = comp_df.round(2)

# Display as a horizontal bar comparison
fig_comp = go.Figure()
fig_comp.add_trace(go.Bar(
    name=selected_team, x=comp_df[selected_team], y=comp_df.index,
    orientation="h", marker_color=PRIMARY,
))
fig_comp.add_trace(go.Bar(
    name=opponent, x=comp_df[opponent], y=comp_df.index,
    orientation="h", marker_color="#E8C547",
))
fig_comp.update_layout(
    barmode="group",
    plot_bgcolor=BG, paper_bgcolor=BG, font_color=TEXT,
    height=300, margin=dict(l=10, r=10, t=10, b=20),
    legend=dict(orientation="h"),
)
st.plotly_chart(fig_comp, use_container_width=True)

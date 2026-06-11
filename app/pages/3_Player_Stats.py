"""
app/pages/3_Player_Stats.py
──────────────────────────────
Per-90 leaderboards and player radar comparisons.
Data: StatsBomb historical + live tournament scorers.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import pandas as pd

from data.ingest.statsbomb_loader import StatsBombLoader, COMPETITIONS
from app.utils.charts import player_radar

st.set_page_config(page_title="Player Stats · WC 2026", page_icon="👤", layout="wide")
st.title("👤 Player Stats")
st.caption("Per-90-minute rates · StatsBomb WC 2022 historical data")

BG, TEXT = "#0F0F23", "#FAFAFA"

# ── Data loading ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner="Building player stats (this takes ~60 seconds first run) …")
def load_player_stats() -> pd.DataFrame:
    loader = StatsBombLoader()
    comp = COMPETITIONS["wc_2022"]
    return loader.get_player_tournament_stats(
        competition_id=comp["competition_id"],
        season_id=comp["season_id"],
        min_minutes=45,
    )

try:
    players_df = load_player_stats()
    data_loaded = not players_df.empty
except Exception as e:
    st.error(f"Error loading player data: {e}")
    data_loaded = False

if not data_loaded:
    st.warning("Player data unavailable. Ensure statsbombpy is installed.")
    st.stop()

# ── Sidebar filters ───────────────────────────────────────────────────────────
st.sidebar.header("Filters")
min_min = st.sidebar.slider("Minimum Minutes Played", 45, 600, 180, step=45)
positions = ["All"] + sorted(players_df["position"].dropna().unique().tolist())
pos_filter = st.sidebar.selectbox("Position", positions)

filtered = players_df[players_df["minutes_played"] >= min_min].copy()
if pos_filter != "All":
    filtered = filtered[filtered["position"] == pos_filter]

# ── Metric selector ───────────────────────────────────────────────────────────
metric_options = {
    "xG / 90":                    "xg_p90",
    "Goals / 90":                 "goals_p90",
    "Assists / 90":               "assists_p90",
    "xA / 90":                    "xa_p90",
    "Pressures / 90":             "pressures_p90",
    "Progressive Passes / 90":    "progressive_passes_p90",
    "Progressive Carries / 90":   "progressive_carries_p90",
    "Key Passes / 90":            "key_passes_p90",
}
metric_label = st.selectbox("Rank players by", list(metric_options.keys()))
metric_col = metric_options[metric_label]

# ── Leaderboard ───────────────────────────────────────────────────────────────
st.subheader(f"🏆 Top 20 — {metric_label}")

if metric_col not in filtered.columns:
    st.warning(f"Metric '{metric_col}' not available in this dataset.")
else:
    top20 = filtered.nlargest(20, metric_col)[
        ["player_name", "team_name", "position", "minutes_played",
         metric_col, "goals_p90", "assists_p90", "xg_p90", "xa_p90"]
    ].copy()

    top20 = top20.rename(columns={
        "player_name": "Player", "team_name": "Team", "position": "Pos",
        "minutes_played": "Mins", metric_col: metric_label,
        "goals_p90": "G/90", "assists_p90": "A/90",
        "xg_p90": "xG/90", "xa_p90": "xA/90",
    })

    st.dataframe(
        top20.round(3),
        hide_index=True,
        use_container_width=True,
        column_config={
            metric_label: st.column_config.ProgressColumn(
                metric_label,
                min_value=0,
                max_value=float(top20[metric_label].max()),
            ),
        },
    )

st.divider()

# ── Player radar comparison ───────────────────────────────────────────────────
st.subheader("🎯 Player Radar Comparison")
col1, col2 = st.columns(2)

all_players = sorted(filtered["player_name"].unique())

with col1:
    player_a = st.selectbox("Player A", all_players, index=0)
    if player_a:
        row_a = filtered[filtered["player_name"] == player_a].iloc[0]
        st.plotly_chart(player_radar(row_a, label=player_a), use_container_width=True)
        st.caption(f"**{player_a}** · {row_a.get('team_name', '')} · {row_a.get('position', '')} · {int(row_a.get('minutes_played', 0))} mins")

with col2:
    player_b_idx = min(1, len(all_players) - 1)
    player_b = st.selectbox("Player B", all_players, index=player_b_idx)
    if player_b:
        row_b = filtered[filtered["player_name"] == player_b].iloc[0]
        st.plotly_chart(player_radar(row_b, label=player_b), use_container_width=True)
        st.caption(f"**{player_b}** · {row_b.get('team_name', '')} · {row_b.get('position', '')} · {int(row_b.get('minutes_played', 0))} mins")

st.divider()

# ── Full stats table ──────────────────────────────────────────────────────────
with st.expander("📋 Full Player Stats Table"):
    display_cols = [c for c in [
        "player_name", "team_name", "position", "minutes_played",
        "goals", "assists", "xg", "xa", "shots",
        "goals_p90", "assists_p90", "xg_p90", "xa_p90",
        "pressures_p90", "progressive_passes_p90",
    ] if c in filtered.columns]

    st.dataframe(
        filtered[display_cols].round(3),
        hide_index=True,
        use_container_width=True,
    )
    st.caption(f"{len(filtered)} players shown · minimum {min_min} minutes")

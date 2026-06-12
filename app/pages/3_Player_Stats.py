"""
app/pages/3_Player_Stats.py
──────────────────────────────
Per-90 leaderboards and percentile-radar comparisons across six tournaments.

Reads from the v_player_stats BI view (PostgreSQL) — instant, no StatsBomb
cold-download. Only metrics with real data are offered (xA and progressive
passes are absent from StatsBomb open data, so they're excluded rather than
shown as misleading zeros).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
import streamlit as st

from app.utils.charts import player_radar
from database.db import engine

st.set_page_config(page_title="Player Stats · WC 2026", page_icon="👤", layout="wide")
st.title("👤 Player Stats")
st.caption("Per-90 leaderboards · percentile radars · six international tournaments")

METRICS = {
    "xG / 90": "xg_p90", "Goals / 90": "goals_p90", "Assists / 90": "assists_p90",
    "Shots / 90": "shots_p90", "Key Passes / 90": "key_passes_p90",
    "Pressures / 90": "pressures_p90",
}


# ── Loaders ───────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner="Loading tournaments …")
def load_tournaments() -> list[str]:
    df = pd.read_sql(
        "SELECT tournament_label, MIN(tournament_year) y FROM v_player_stats "
        "WHERE minutes > 0 GROUP BY tournament_label ORDER BY y DESC", engine)
    return df["tournament_label"].tolist()


@st.cache_data(ttl=3600, show_spinner="Loading player stats …")
def load_players(tournament: str) -> pd.DataFrame:
    return pd.read_sql(
        "SELECT player, position, team, matches_played, minutes, goals, assists, "
        "xg, shots, key_passes, pressures, tackles, goals_p90, assists_p90, "
        "xg_p90, shots_p90, key_passes_p90, pressures_p90 "
        "FROM v_player_stats WHERE tournament_label = %(t)s AND minutes > 0",
        engine, params={"t": tournament})


tournaments = load_tournaments()
if not tournaments:
    st.warning("No player data. Run `python scripts/load_statsbomb_history.py`.")
    st.stop()

# ── Filters ───────────────────────────────────────────────────────────────────
st.sidebar.header("Filters")
tournament = st.sidebar.selectbox(
    "Tournament", tournaments,
    index=tournaments.index("WC 2022") if "WC 2022" in tournaments else 0)
players_df = load_players(tournament)

max_min = int(players_df["minutes"].max()) if not players_df.empty else 600
min_min = st.sidebar.slider("Minimum minutes", 45, max_min, min(180, max_min), step=45)
positions = ["All"] + sorted(players_df["position"].dropna().unique().tolist())
pos_filter = st.sidebar.selectbox("Position", positions)

filtered = players_df[players_df["minutes"] >= min_min].copy()
if pos_filter != "All":
    filtered = filtered[filtered["position"] == pos_filter]

if filtered.empty:
    st.info("No players match these filters — lower the minutes threshold.")
    st.stop()

# ── Leaderboard ───────────────────────────────────────────────────────────────
metric_label = st.selectbox("Rank players by", list(METRICS.keys()))
metric_col = METRICS[metric_label]
st.subheader(f"🏆 Top 20 — {metric_label}")

# Columns to show: identity + ranked metric + a few standard per-90s (deduped,
# since the ranked metric may already be one of them).
base_cols = ["player", "team", "position", "minutes", metric_col,
             "goals_p90", "assists_p90", "xg_p90"]
cols = list(dict.fromkeys(base_cols))   # preserve order, drop duplicates
top20 = filtered.nlargest(20, metric_col)[cols].round(3)

labels = {"player": "Player", "team": "Team", "position": "Pos", "minutes": "Mins",
          "goals_p90": "G/90", "assists_p90": "A/90", "xg_p90": "xG/90",
          metric_col: metric_label}
config = {c: labels.get(c, c) for c in cols}
config[metric_col] = st.column_config.ProgressColumn(
    metric_label, min_value=0, max_value=float(top20[metric_col].max() or 1))

st.dataframe(top20, hide_index=True, use_container_width=True, column_config=config)

st.divider()

# ── Radar comparison (percentile ranks within the filtered pool) ──────────────
st.subheader("🎯 Player Radar Comparison")
st.caption("Each axis is the player's percentile rank within the current filter — "
           "so the shape shows what they're *relatively* elite at.")
all_players = sorted(filtered["player"].unique())
c1, c2 = st.columns(2)
for col, default in ((c1, 0), (c2, min(1, len(all_players) - 1))):
    with col:
        name = st.selectbox(f"Player {'A' if default == 0 else 'B'}", all_players,
                            index=default, key=f"p{default}")
        row = filtered[filtered["player"] == name].iloc[0]
        st.plotly_chart(player_radar(row, pool=filtered, label=name),
                        use_container_width=True)
        st.caption(f"**{name}** · {row['team']} · {row['position']} · {int(row['minutes'])} mins")

st.divider()

# ── Full table ────────────────────────────────────────────────────────────────
with st.expander("📋 Full player stats table"):
    st.dataframe(filtered.round(3), hide_index=True, use_container_width=True)
    st.caption(f"{len(filtered)} players · minimum {min_min} minutes · {tournament}")

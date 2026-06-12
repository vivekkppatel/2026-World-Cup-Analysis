"""
app/pages/5_Player_Valuation.py
─────────────────────────────────
Composite Player Contribution Score (CPCS) —
identifying undervalued players by position.

The finance analogy: CPCS is risk-adjusted return per unit of exposure
(minutes). High CPCS + low minutes = alpha opportunity.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import pandas as pd

from data.ingest.statsbomb_loader import StatsBombLoader, COMPETITIONS
from models.player_rating import compute_player_ratings, get_undervalued_players
from app.utils.charts import cpcs_scatter, player_radar

from app.utils.theme import inject_theme

st.set_page_config(page_title="Player Valuation · WC 2026", page_icon="💰", layout="wide")
inject_theme()
st.title("💰 Player Valuation")
st.subheader("Composite Player Contribution Score (CPCS)")
st.caption(
    "Position-adjusted, per-90 weighted scoring model. "
    "High CPCS + low minutes = undervalued player. "
    "StatsBomb event data — select a tournament in the sidebar."
)

BG, TEXT, PRIMARY, ACCENT = "#0F0F23", "#FAFAFA", "#00A86B", "#E8C547"

# ── Data loading ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner="Computing player ratings …")
def load_rated_players(tournament_key: str, min_minutes: int = 90) -> pd.DataFrame:
    comp = COMPETITIONS[tournament_key]
    raw = StatsBombLoader.get_player_tournament_stats(
        competition_id=comp["competition_id"],
        season_id=comp["season_id"],
        min_minutes=min_minutes,
    )
    if raw.empty:
        return raw
    return compute_player_ratings(raw, min_minutes=min_minutes)

tournament_key = st.sidebar.selectbox(
    "Tournament",
    options=list(COMPETITIONS),
    format_func=lambda k: COMPETITIONS[k]["label"],
    index=list(COMPETITIONS).index("wc_2022"),
)
min_min = st.sidebar.slider("Min Minutes Played", 45, 400, 90, step=45)

try:
    rated_df = load_rated_players(tournament_key, min_min)
    data_loaded = not rated_df.empty
except Exception as e:
    st.error(f"Error: {e}")
    data_loaded = False

if not data_loaded:
    st.warning("Could not load player data. Ensure statsbombpy is installed.")
    st.stop()

# ── Model explainer ───────────────────────────────────────────────────────────
with st.expander("ℹ️ How is CPCS calculated?"):
    st.markdown("""
    **Composite Player Contribution Score (CPCS)** is computed in three steps:

    1. **Per-90 rates** — All volume metrics (goals, assists, pressures, etc.)
       are normalised to 90-minute rates to remove playing-time bias.

    2. **Feature normalisation** — Each metric is scaled 0–1 across all
       players in the dataset so no single metric dominates.

    3. **Position-adjusted weighting** — A forward's goals and xG receive
       higher weight; a defender's pressures and tackles receive higher weight.
       Weights are inspired by StatsBomb's publicly documented methodology.

    Final scores are scaled 0–100 for readability.
    """)

st.divider()

# ── Top CPCS leaderboard ──────────────────────────────────────────────────────
st.subheader("🏆 Overall CPCS Leaderboard")

leaderboard_cols = ["player_name", "team_name", "position_group", "minutes_played", "cpcs",
                    "goals_p90", "assists_p90", "xg_p90", "pressures_p90"]
leaderboard_cols = [c for c in leaderboard_cols if c in rated_df.columns]

top30 = rated_df.head(30)[leaderboard_cols].copy()
top30 = top30.rename(columns={
    "player_name": "Player", "team_name": "Team",
    "position_group": "Pos Group", "minutes_played": "Mins",
    "cpcs": "CPCS", "goals_p90": "G/90",
    "assists_p90": "A/90", "xg_p90": "xG/90", "pressures_p90": "Press/90",
})

st.dataframe(
    top30.round(2),
    hide_index=True,
    use_container_width=True,
    column_config={
        "CPCS": st.column_config.ProgressColumn(
            "CPCS (0–100)", min_value=0, max_value=100,
        ),
    },
)

st.divider()

# ── CPCS Scatter ──────────────────────────────────────────────────────────────
st.subheader("🔍 CPCS vs Minutes Played — Find Undervalued Players")
st.caption("Top-left quadrant = high contribution, low minutes = undervalued")

if "cpcs" in rated_df.columns:
    st.plotly_chart(cpcs_scatter(rated_df), use_container_width=True)

st.divider()

# ── Undervalued players ───────────────────────────────────────────────────────
st.subheader("⭐ Undervalued Players")
st.caption(
    "Players with above-median CPCS but below-median minutes. "
    "High output-per-input — the tournament's hidden gems."
)

try:
    undervalued = get_undervalued_players(rated_df, top_n=10)
    if not undervalued.empty:
        uv_cols = [c for c in ["player_name", "team_name", "position_group",
                                "minutes_played", "cpcs", "efficiency_ratio",
                                "xg_p90", "goals_p90"] if c in undervalued.columns]
        uv_display = undervalued[uv_cols].rename(columns={
            "player_name": "Player", "team_name": "Team",
            "position_group": "Pos", "minutes_played": "Mins",
            "cpcs": "CPCS", "efficiency_ratio": "CPCS / 90",
            "xg_p90": "xG/90", "goals_p90": "G/90",
        })
        st.dataframe(uv_display.round(2), hide_index=True, use_container_width=True)
    else:
        st.info("No undervalued players found with current filters.")
except Exception as e:
    st.error(f"Could not compute undervalued list: {e}")

st.divider()

# ── Position group breakdown ──────────────────────────────────────────────────
st.subheader("📊 CPCS by Position")
pos_tabs = st.tabs(["⚔️ Forwards", "🔵 Midfielders", "🛡️ Defenders", "🧤 Goalkeepers"])
pos_map = {"⚔️ Forwards": "FWD", "🔵 Midfielders": "MID",
           "🛡️ Defenders": "DEF", "🧤 Goalkeepers": "GK"}

for tab, (label, group) in zip(pos_tabs, pos_map.items()):
    with tab:
        pos_df = rated_df[rated_df.get("position_group", pd.Series()) == group].head(10) if "position_group" in rated_df.columns else rated_df.head(10)
        if pos_df.empty:
            st.info(f"No data for {label}")
            continue

        col_a, col_b = st.columns([1.5, 1])
        with col_a:
            display = pos_df[leaderboard_cols].rename(columns={
                "player_name": "Player", "team_name": "Team",
                "position_group": "Pos", "minutes_played": "Mins",
                "cpcs": "CPCS",
            }).head(10)
            st.dataframe(display.round(2), hide_index=True, use_container_width=True)

        with col_b:
            if not pos_df.empty:
                top_player = pos_df.iloc[0]
                st.markdown(f"**{top_player.get('player_name', 'N/A')}** — Top {label[2:]}")
                st.metric("CPCS", f"{top_player.get('cpcs', 0):.1f} / 100")
                st.plotly_chart(player_radar(top_player), use_container_width=True)

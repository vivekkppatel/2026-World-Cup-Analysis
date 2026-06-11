"""
app/pages/4_Match_Predictor.py
────────────────────────────────
Win probability model for any two teams.
Model trained on WC 2018 + 2022 StatsBomb data.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import pandas as pd

from models.match_predictor import MatchPredictor, MODEL_PATH
from data.ingest.statsbomb_loader import StatsBombLoader, COMPETITIONS
from app.utils.charts import win_probability_gauge

st.set_page_config(page_title="Match Predictor · WC 2026", page_icon="🔮", layout="wide")
st.title("🔮 Match Predictor")
st.caption("Logistic Regression model trained on StatsBomb WC 2018 & 2022 event data")

BG, TEXT, PRIMARY = "#0F0F23", "#FAFAFA", "#00A86B"

# ── Load model & team stats ───────────────────────────────────────────────────
@st.cache_resource(show_spinner="Loading prediction model …")
def load_predictor() -> MatchPredictor | None:
    try:
        return MatchPredictor.from_disk(MODEL_PATH)
    except FileNotFoundError:
        return None

@st.cache_data(ttl=3600, show_spinner="Loading team stats for predictions …")
def load_team_averages() -> dict[str, dict]:
    """Build average xG, shots, etc. per team from historical WC 2022 data."""
    comp = COMPETITIONS["wc_2022"]
    df = StatsBombLoader.get_team_match_stats(comp["competition_id"], comp["season_id"])
    if df.empty:
        return {}
    agg = df.groupby("team").agg(
        avg_xg=("xg", "mean"),
        avg_shots=("shots", "mean"),
        avg_passes=("passes", "mean"),
        avg_pressures=("pressures", "mean"),
        avg_goals_for=("goals_for", "mean"),
        avg_goals_against=("goals_against", "mean"),
    ).to_dict("index")
    return agg

predictor = load_predictor()

try:
    team_averages = load_team_averages()
    teams = sorted(team_averages.keys())
    stats_loaded = bool(teams)
except Exception:
    teams = []
    team_averages = {}
    stats_loaded = False

# ── Model status ──────────────────────────────────────────────────────────────
if predictor is None:
    st.warning(
        "⚠️ Model not trained yet. Run `python scripts/train_model.py` to train it. "
        "You can still explore team stats and manually adjust the sliders below."
    )

st.divider()

# ── Team selectors ────────────────────────────────────────────────────────────
st.subheader("Select Teams")
col_home, col_vs, col_away = st.columns([2, 0.5, 2])

with col_home:
    if teams:
        home_team = st.selectbox("🏠 Home Team", teams, index=0)
    else:
        home_team = st.text_input("Home Team", "Brazil")

with col_vs:
    st.markdown("<br><br><h3 style='text-align:center;color:#8B8FA8'>VS</h3>", unsafe_allow_html=True)

with col_away:
    if teams:
        away_idx = min(1, len(teams) - 1)
        away_team = st.selectbox("✈️ Away Team", teams, index=away_idx)
    else:
        away_team = st.text_input("Away Team", "France")

is_knockout = st.checkbox("Knockout stage?", value=False)

st.divider()

# ── Manual stat overrides ─────────────────────────────────────────────────────
st.subheader("⚙️ Match Parameters")
st.caption("Pre-filled from historical averages — adjust as needed.")

home_stats = team_averages.get(home_team, {})
away_stats  = team_averages.get(away_team, {})

col_h, col_a = st.columns(2)

with col_h:
    st.markdown(f"**{home_team}**")
    home_xg    = st.slider(f"Expected xG", 0.0, 4.0, float(home_stats.get("avg_xg", 1.5)), 0.05, key="hxg")
    home_shots = st.slider(f"Expected Shots", 0, 30, int(home_stats.get("avg_shots", 12)), key="hshots")

with col_a:
    st.markdown(f"**{away_team}**")
    away_xg    = st.slider(f"Expected xG", 0.0, 4.0, float(away_stats.get("avg_xg", 1.2)), 0.05, key="axg")
    away_shots = st.slider(f"Expected Shots", 0, 30, int(away_stats.get("avg_shots", 10)), key="ashots")

st.divider()

# ── Prediction ────────────────────────────────────────────────────────────────
st.subheader("📊 Prediction")

if predictor:
    try:
        probs = predictor.predict_proba(
            xg_diff=home_xg - away_xg,
            shots_diff=home_shots - away_shots,
            goals_for_home=home_stats.get("avg_goals_for", 1.5),
            goals_for_away=away_stats.get("avg_goals_for", 1.2),
            goals_ag_home=home_stats.get("avg_goals_against", 1.0),
            goals_ag_away=away_stats.get("avg_goals_against", 1.2),
            is_knockout=int(is_knockout),
        )

        # Probability gauge
        st.plotly_chart(
            win_probability_gauge(
                probs["HOME_WIN"], probs["DRAW"], probs["AWAY_WIN"],
                home_team, away_team,
            ),
            use_container_width=True,
        )

        # Verdict
        max_outcome = max(probs, key=probs.get)
        verdict_map = {
            "HOME_WIN": (home_team, PRIMARY),
            "DRAW":     ("Draw", "#8B8FA8"),
            "AWAY_WIN": (away_team, "#E8C547"),
        }
        verdict_label, verdict_color = verdict_map[max_outcome]
        st.markdown(
            f"<h2 style='color:{verdict_color}; text-align:center;'>"
            f"Predicted: {verdict_label} ({probs[max_outcome]*100:.1f}%)</h2>",
            unsafe_allow_html=True,
        )

        # Probability breakdown
        prob_cols = st.columns(3)
        prob_cols[0].metric(f"{home_team} Win", f"{probs['HOME_WIN']*100:.1f}%")
        prob_cols[1].metric("Draw",             f"{probs['DRAW']*100:.1f}%")
        prob_cols[2].metric(f"{away_team} Win",  f"{probs['AWAY_WIN']*100:.1f}%")

    except Exception as e:
        st.error(f"Prediction failed: {e}")
else:
    # Show raw xG advantage without model
    xg_diff = home_xg - away_xg
    if xg_diff > 0.3:
        st.info(f"📊 xG advantage: **{home_team}** (+{xg_diff:.2f} xG). Train the model for win probabilities.")
    elif xg_diff < -0.3:
        st.info(f"📊 xG advantage: **{away_team}** ({xg_diff:.2f} xG). Train the model for win probabilities.")
    else:
        st.info(f"📊 Evenly matched on xG (diff: {xg_diff:.2f}). Train the model for win probabilities.")

st.divider()
st.caption(
    "Model: Logistic Regression with StandardScaler · "
    "Features: xG diff, shots diff, goals scored/conceded, stage · "
    "Training data: StatsBomb WC 2018 + WC 2022"
)

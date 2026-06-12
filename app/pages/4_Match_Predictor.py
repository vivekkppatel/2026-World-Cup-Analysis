"""
app/pages/4_Match_Predictor.py
────────────────────────────────
Win-probability predictor for any two teams, using the leakage-free
logistic-regression model (Elo + FIFA rank + recent form).

Every feature shown is one the model actually uses and that would be known
before kickoff — no peeking at the match's own stats. The model was validated
on a strict temporal hold-out (train pre-2022 → test WC 2022); see
scripts/train_model.py for the honest metrics.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
import streamlit as st
from sqlalchemy import text

from app.utils.charts import win_probability_gauge
from data.transform.team_aliases import canonicalize
from database.db import engine
from models.elo import build_from_history
from models.match_predictor import MatchPredictor, MODEL_PATH

st.set_page_config(page_title="Match Predictor · WC 2026", page_icon="🔮", layout="wide")
st.title("🔮 Match Predictor")
st.caption("Leakage-free logistic regression · features: Elo, FIFA rank, recent form")

BG, TEXT, PRIMARY, GOLD, MUTED = "#0F0F23", "#FAFAFA", "#00A86B", "#E8C547", "#8B8FA8"
FJELSTUL = Path(__file__).parent.parent.parent / "data" / "external" / "fjelstul" / "matches.csv"


# ── Loaders ───────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner="Loading model …")
def load_predictor() -> MatchPredictor | None:
    try:
        return MatchPredictor.from_disk(MODEL_PATH)
    except FileNotFoundError:
        return None


@st.cache_resource(show_spinner="Building Elo ratings …")
def load_elo():
    df = pd.read_csv(FJELSTUL)
    df["home_team_name"] = df["home_team_name"].map(canonicalize)
    df["away_team_name"] = df["away_team_name"].map(canonicalize)
    return build_from_history(df)


@st.cache_data(ttl=3600, show_spinner="Loading teams …")
def load_team_meta() -> pd.DataFrame:
    """WC 2026 teams with FIFA rank and a recent-form proxy (avg goal/xG diff)."""
    sql = """
        SELECT t.name AS team, t.group_name, t.fifa_ranking,
               AVG(s.goals_scored - s.goals_conceded) AS form_goals,
               AVG(s.team_xg) AS avg_xg
        FROM teams t
        LEFT JOIN v_team_match_stats s ON s.team = t.name
        WHERE t.group_name IS NOT NULL
        GROUP BY t.name, t.group_name, t.fifa_ranking
        ORDER BY t.name
    """
    return pd.read_sql(sql, engine)


predictor = load_predictor()
if predictor is None:
    st.warning("⚠️ Model not trained. Run `python scripts/train_model.py` first.")
    st.stop()

try:
    elo = load_elo()
    meta = load_team_meta()
    teams = meta["team"].tolist()
except Exception as e:
    st.error(f"Could not load supporting data: {e}")
    st.stop()

meta_by_team = {r["team"]: r for _, r in meta.iterrows()}


# ── Team selectors ────────────────────────────────────────────────────────────
st.subheader("Select teams")
c_home, c_vs, c_away = st.columns([2, 0.4, 2])
with c_home:
    home_team = st.selectbox("🏠 Team A", teams, index=0)
with c_vs:
    st.markdown(f"<br><br><h3 style='text-align:center;color:{MUTED}'>vs</h3>",
                unsafe_allow_html=True)
with c_away:
    away_team = st.selectbox("✈️ Team B", teams, index=min(1, len(teams) - 1))

is_knockout = st.checkbox("Knockout match? (no draws — affects the model's stage feature)")

if home_team == away_team:
    st.info("Pick two different teams.")
    st.stop()


# ── Assemble the model's pre-match features ───────────────────────────────────
hm, am = meta_by_team[home_team], meta_by_team[away_team]
elo_a, elo_b = elo.rating(home_team), elo.rating(away_team)
rank_a = int(hm["fifa_ranking"]) if pd.notna(hm["fifa_ranking"]) else None
rank_b = int(am["fifa_ranking"]) if pd.notna(am["fifa_ranking"]) else None

st.divider()
st.subheader("⚙️ Pre-match features")
st.caption("Computed from data known before kickoff. Tweak the form sliders to explore.")

f1, f2 = st.columns(2)
with f1:
    st.markdown(f"**{home_team}** · Elo {elo_a:.0f} · FIFA #{rank_a or '—'}")
    form_a = st.slider("Recent goal diff / match", -3.0, 3.0,
                       float(hm["form_goals"]) if pd.notna(hm["form_goals"]) else 0.0,
                       0.1, key="fa")
with f2:
    st.markdown(f"**{away_team}** · Elo {elo_b:.0f} · FIFA #{rank_b or '—'}")
    form_b = st.slider("Recent goal diff / match", -3.0, 3.0,
                       float(am["form_goals"]) if pd.notna(am["form_goals"]) else 0.0,
                       0.1, key="fb")

xg_a = float(hm["avg_xg"]) if pd.notna(hm["avg_xg"]) else 1.3
xg_b = float(am["avg_xg"]) if pd.notna(am["avg_xg"]) else 1.3

features = {
    "elo_diff": elo_a - elo_b,
    "fifa_rank_gap": float((rank_b or 50) - (rank_a or 50)),
    "form_goals_diff": form_a - form_b,
    "form_xg_diff": xg_a - xg_b,
    "rest_days_diff": 0.0,   # assume equal rest in a what-if matchup
    "is_knockout": int(is_knockout),
}

fcols = st.columns(len(features))
for col, (name, val) in zip(fcols, features.items()):
    col.metric(name, f"{val:+.0f}" if abs(val) >= 5 else f"{val:+.2f}")

st.divider()


# ── Prediction ────────────────────────────────────────────────────────────────
st.subheader("📊 Prediction")
probs = predictor.predict_one(features)

st.plotly_chart(
    win_probability_gauge(probs["HOME_WIN"], probs["DRAW"], probs["AWAY_WIN"],
                          home_team, away_team),
    use_container_width=True,
)

verdict = max(probs, key=probs.get)
vmap = {"HOME_WIN": (home_team, PRIMARY), "DRAW": ("Draw", MUTED),
        "AWAY_WIN": (away_team, GOLD)}
label, color = vmap[verdict]
st.markdown(f"<h2 style='color:{color};text-align:center'>"
            f"Predicted: {label} ({probs[verdict]*100:.1f}%)</h2>",
            unsafe_allow_html=True)

pc = st.columns(3)
pc[0].metric(f"{home_team} win", f"{probs['HOME_WIN']*100:.1f}%")
pc[1].metric("Draw", f"{probs['DRAW']*100:.1f}%")
pc[2].metric(f"{away_team} win", f"{probs['AWAY_WIN']*100:.1f}%")

if is_knockout:
    st.caption("Knockout: a draw resolves via extra time / penalties — the draw "
               "probability above would split between the two sides on the day.")

st.divider()
with st.expander("ℹ️ How this model works — and why it's honest"):
    st.markdown("""
**Multinomial logistic regression** over six pre-match features:
`elo_diff`, `fifa_rank_gap`, `form_goals_diff`, `form_xg_diff`,
`rest_days_diff`, `is_knockout`.

**Why every feature is leakage-free:** each is knowable *before* kickoff —
Elo is built only from matches *before* this one, form is a rolling average of
*prior* games. The earlier version of this model leaked the match's own goals
and xG into its features, producing a meaningless 96.9% accuracy. This one is
validated on a **strict temporal hold-out** (trained on pre-2022 tournaments,
tested on WC 2022 it had never seen) and reports **log loss, Brier score, and
calibration** — the metrics that matter for a probabilistic forecast.

**Finance analogy:** this is point-in-time correctness — the same discipline as
backtesting only on fundamentals that were public on the trade date, never
restated numbers.
""")

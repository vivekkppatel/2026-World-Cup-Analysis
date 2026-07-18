"""
app/pages/7_Regression_Analysis.py
────────────────────────────────────
Full statistical regression analysis of the WC 2026 match-outcome model.

Shows the analyst-grade output: coefficients with odds ratios, pseudo-R²,
calibration curves, feature importance, confusion matrix, and the model's
predicted probability distribution across all WC 2026 group-stage matches.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import streamlit as st
from sklearn.metrics import (
    accuracy_score, brier_score_loss, log_loss,
    confusion_matrix, classification_report,
)
from sqlalchemy import text

from app.utils.theme import inject_theme
from database.db import engine, health_check
from data.transform.team_aliases import canonicalize
from models.elo import build_from_history
from models.features import build_match_features, FEATURE_COLUMNS
from models.match_predictor import MatchPredictor, MODEL_PATH, MODEL_VERSION

st.set_page_config(page_title="Regression Analysis · WC 2026", page_icon="📊", layout="wide")
inject_theme()

BG, PANEL, TEXT = "#0F0F23", "#1A1A2E", "#FAFAFA"
PRIMARY, ACCENT, PURPLE, RED, LIME = "#00A86B", "#E8C547", "#6D28D9", "#E0003C", "#9BE800"
MUTED = "#8B8FA8"
CLASS_LABELS = ["HOME_WIN", "DRAW", "AWAY_WIN"]
CLASS_COLORS = [PRIMARY, MUTED, PURPLE]

FJELSTUL = Path(__file__).parent.parent.parent / "data" / "external" / "fjelstul" / "matches.csv"

ALL_TOURNAMENTS = ["WC 2018", "EURO 2020", "WC 2022",
                   "AFCON 2023", "COPA 2024", "EURO 2024"]
TRAIN_TOURNAMENTS = ["WC 2018", "EURO 2020"]
TEST_TOURNAMENTS = ["WC 2022"]

_MATCH_SQL = """
    SELECT m.kickoff_utc, m.stage, m.winner, m.tournament_label,
           th.name AS home_team, ta.name AS away_team,
           m.home_score, m.away_score,
           xh.team_xg AS team_xg_home, xa.team_xg AS team_xg_away
    FROM matches m
    JOIN teams th ON th.id = m.home_team_id
    JOIN teams ta ON ta.id = m.away_team_id
    LEFT JOIN (SELECT match_id, team_id, SUM(xg) AS team_xg
               FROM player_match_stats GROUP BY match_id, team_id) xh
           ON xh.match_id = m.id AND xh.team_id = m.home_team_id
    LEFT JOIN (SELECT match_id, team_id, SUM(xg) AS team_xg
               FROM player_match_stats GROUP BY match_id, team_id) xa
           ON xa.match_id = m.id AND xa.team_id = m.away_team_id
    WHERE m.tournament_label = ANY(%(labels)s)
      AND m.status = 'FINISHED' AND m.winner IS NOT NULL
    ORDER BY m.kickoff_utc
"""


def _plotly_layout(fig: go.Figure, **kwargs) -> go.Figure:
    fig.update_layout(
        plot_bgcolor=BG, paper_bgcolor=BG, font_color=TEXT,
        margin=dict(l=40, r=30, t=50, b=40),
        legend=dict(bgcolor="rgba(0,0,0,0)", font_color=TEXT),
        **kwargs,
    )
    return fig


st.title("📊 Regression Analysis")
st.caption("Multinomial logistic regression · leakage-free temporal validation · "
           f"model `{MODEL_VERSION}`")


@st.cache_data(ttl=3600, show_spinner="Loading match data …")
def load_data():
    matches = pd.read_sql(_MATCH_SQL, engine, params={"labels": ALL_TOURNAMENTS})
    with engine.connect() as conn:
        fifa_ranks = {n: r for n, r in conn.execute(
            text("SELECT name, fifa_ranking FROM teams WHERE fifa_ranking IS NOT NULL")
        ).fetchall()}
    history = pd.read_csv(FJELSTUL)
    history["home_team_name"] = history["home_team_name"].map(canonicalize)
    history["away_team_name"] = history["away_team_name"].map(canonicalize)
    elo = build_from_history(history)
    return matches, elo, fifa_ranks


try:
    if not health_check():
        st.error("Cannot connect to database.")
        st.stop()
    matches_raw, elo, fifa_ranks = load_data()
except Exception as e:
    st.error(f"Could not load data: {e}")
    st.stop()

if matches_raw.empty:
    st.error("No match data found. Run the data pipeline first.")
    st.stop()

X_all, y_all, meta = build_match_features(matches_raw, elo, fifa_ranks)
tour = meta["tournament_label"]
train_mask = tour.isin(TRAIN_TOURNAMENTS)
test_mask = tour.isin(TEST_TOURNAMENTS)
X_train, y_train = X_all[train_mask], y_all[train_mask]
X_test, y_test = X_all[test_mask], y_all[test_mask]

model = MatchPredictor()
model.train(X_train, y_train)
metrics = model.evaluate(X_test, y_test)
baseline_acc = MatchPredictor.baseline_accuracy(X_test, y_test)

idx_to_label = {0: "HOME_WIN", 1: "DRAW", 2: "AWAY_WIN"}


# ════════════════════════════════════════════════════════════════════════════
# 1. KPI header
# ════════════════════════════════════════════════════════════════════════════
st.divider()
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Accuracy (WC 2022)", f"{metrics['accuracy']*100:.1f}%",
          f"+{(metrics['accuracy']-baseline_acc)*100:.1f} pts vs baseline")
k2.metric("Log Loss", f"{metrics['log_loss']:.3f}", "lower is better",
          delta_color="inverse")
k3.metric("Brier Score", f"{metrics['brier']:.3f}", "lower is better",
          delta_color="inverse")
k4.metric("Train set", f"{len(X_train)} matches",
          f"{', '.join(TRAIN_TOURNAMENTS)}")
k5.metric("Test set", f"{len(X_test)} matches",
          f"{', '.join(TEST_TOURNAMENTS)}")

st.divider()


# ════════════════════════════════════════════════════════════════════════════
# 2. Coefficients & odds ratios
# ════════════════════════════════════════════════════════════════════════════
st.subheader("⚙️ Regression coefficients")
st.caption("Standardised multinomial logistic regression coefficients. "
           "Positive = increases that outcome's log-odds. "
           "Odds ratio = exp(β): how much the odds multiply per 1 SD change in the feature.")

clf = model.pipeline.named_steps["clf"]
scaler = model.pipeline.named_steps["scaler"]
coef_df = pd.DataFrame(clf.coef_, columns=FEATURE_COLUMNS,
                       index=[idx_to_label[c] for c in clf.classes_])

col_coef, col_or = st.columns(2)

with col_coef:
    fig_coef = go.Figure()
    for i, cls in enumerate(coef_df.index):
        fig_coef.add_trace(go.Bar(
            name=cls, y=FEATURE_COLUMNS, x=coef_df.loc[cls].values,
            orientation="h", marker_color=CLASS_COLORS[i],
        ))
    _plotly_layout(fig_coef, title="Standardised coefficients (β)",
                   barmode="group", height=380,
                   xaxis_title="Coefficient value", yaxis_title="")
    st.plotly_chart(fig_coef, use_container_width=True)

with col_or:
    odds_df = np.exp(coef_df).round(3)
    fig_or = go.Figure()
    for i, cls in enumerate(odds_df.index):
        fig_or.add_trace(go.Bar(
            name=cls, y=FEATURE_COLUMNS, x=odds_df.loc[cls].values,
            orientation="h", marker_color=CLASS_COLORS[i],
        ))
    fig_or.add_vline(x=1.0, line_dash="dash", line_color=ACCENT, annotation_text="neutral")
    _plotly_layout(fig_or, title="Odds ratios — exp(β)",
                   barmode="group", height=380,
                   xaxis_title="Odds ratio", yaxis_title="")
    st.plotly_chart(fig_or, use_container_width=True)

st.markdown(f"""
<div style="background:{PANEL};border:1px solid #2D2D4E;border-radius:10px;padding:.8rem 1rem;margin-bottom:1rem;">
  <span style="color:{LIME};font-weight:700">Reading the coefficients:</span>
  <span style="color:{TEXT};font-size:.88rem">
    A positive <code>elo_diff</code> coefficient for HOME_WIN means that when the home team
    has a higher Elo rating, the model's predicted log-odds of a home win increase.
    The odds ratio tells you the multiplier: an OR of 1.8 means 80% higher odds
    per 1 SD of Elo advantage. Values &lt; 1 mean the feature reduces that outcome's odds.
  </span>
</div>
""", unsafe_allow_html=True)

# Features as rows, classes as columns. Prefix the class columns so β and OR
# blocks stay unique (concat with identical column labels → pyarrow rejects it).
coef_t = coef_df.T.rename(columns=lambda c: f"β · {c}")
or_t = odds_df.T.rename(columns=lambda c: f"OR · {c}")
combined = pd.concat([coef_t, or_t], axis=1)
combined.index.name = "Feature"
st.dataframe(combined.style.format("{:.3f}"), use_container_width=True)

st.divider()


# ════════════════════════════════════════════════════════════════════════════
# 3. Feature importance (absolute coefficient magnitude)
# ════════════════════════════════════════════════════════════════════════════
st.subheader("📐 Feature importance")
st.caption("Mean absolute coefficient across all three outcome classes — "
           "higher means the feature has more influence on predictions.")

importance = coef_df.abs().mean(axis=0).sort_values(ascending=True)
fig_imp = go.Figure(go.Bar(
    y=importance.index, x=importance.values,
    orientation="h",
    marker=dict(color=importance.values,
                colorscale=[[0, PURPLE], [0.5, RED], [1, LIME]]),
    text=[f"{v:.3f}" for v in importance.values],
    textposition="outside",
))
_plotly_layout(fig_imp, title="Mean |β| across classes", height=320,
               xaxis_title="Mean absolute coefficient", yaxis_title="")
st.plotly_chart(fig_imp, use_container_width=True)

st.divider()


# ════════════════════════════════════════════════════════════════════════════
# 4. Confusion matrix (held-out WC 2022)
# ════════════════════════════════════════════════════════════════════════════
st.subheader("🎯 Confusion matrix — WC 2022 hold-out")
st.caption("Rows = actual outcome, columns = predicted. "
           "Diagonal cells are correct predictions.")

X_test_scaled = X_test[FEATURE_COLUMNS].fillna(0.0)
y_pred = model.pipeline.predict(X_test_scaled)
cm = confusion_matrix(y_test, y_pred, labels=[0, 1, 2])

fig_cm = go.Figure(go.Heatmap(
    z=cm, x=CLASS_LABELS, y=CLASS_LABELS,
    colorscale=[[0, "#14142B"], [1, LIME]],
    text=cm, texttemplate="%{text}",
    textfont=dict(size=18, color=TEXT),
    showscale=False,
))
_plotly_layout(fig_cm, title="Predicted vs actual (WC 2022)",
               xaxis_title="Predicted", yaxis_title="Actual",
               height=380, width=480)
fig_cm.update_xaxes(side="bottom")

col_cm, col_report = st.columns([1, 1])
with col_cm:
    st.plotly_chart(fig_cm, use_container_width=True)

with col_report:
    report = classification_report(y_test, y_pred, target_names=CLASS_LABELS,
                                   output_dict=True)
    report_df = pd.DataFrame(report).T
    report_df = report_df.loc[CLASS_LABELS + ["macro avg", "weighted avg"]]
    report_df = report_df[["precision", "recall", "f1-score", "support"]]
    report_df["support"] = report_df["support"].astype(int)
    st.markdown("**Classification report**")
    st.dataframe(report_df.style.format({
        "precision": "{:.2f}", "recall": "{:.2f}", "f1-score": "{:.2f}",
    }), use_container_width=True)

st.divider()


# ════════════════════════════════════════════════════════════════════════════
# 5. Calibration curve
# ════════════════════════════════════════════════════════════════════════════
st.subheader("📈 Calibration curve")
st.caption("A well-calibrated model's predicted confidence matches the observed hit rate. "
           "Points on the diagonal = perfect calibration.")

proba_test = model.pipeline.predict_proba(X_test_scaled)
top_conf = proba_test.max(axis=1)
top_pred = proba_test.argmax(axis=1)
y_arr = np.asarray(y_test)
hits = (top_pred == y_arr).astype(float)

n_bins = 8
bins = np.linspace(0.0, 1.0, n_bins + 1)
cal_data = []
for lo, hi in zip(bins[:-1], bins[1:]):
    mask = (top_conf >= lo) & (top_conf < (hi if hi < 1.0 else hi + 0.01))
    if mask.sum() == 0:
        continue
    cal_data.append({
        "mean_conf": float(top_conf[mask].mean()),
        "hit_rate": float(hits[mask].mean()),
        "n": int(mask.sum()),
    })

cal_df = pd.DataFrame(cal_data)
fig_cal = go.Figure()
fig_cal.add_trace(go.Scatter(
    x=[0, 1], y=[0, 1], mode="lines",
    line=dict(color=MUTED, dash="dash"), name="Perfect",
))
fig_cal.add_trace(go.Scatter(
    x=cal_df["mean_conf"], y=cal_df["hit_rate"],
    mode="markers+lines",
    marker=dict(size=cal_df["n"] / cal_df["n"].max() * 20 + 6, color=LIME),
    line=dict(color=LIME),
    name="Model",
    text=[f"n={n}" for n in cal_df["n"]],
    hovertemplate="Confidence: %{x:.2f}<br>Hit rate: %{y:.2f}<br>%{text}<extra></extra>",
))
_plotly_layout(fig_cal, title="Reliability diagram (top-prediction confidence)",
               xaxis_title="Mean predicted confidence",
               yaxis_title="Observed hit rate", height=400)
st.plotly_chart(fig_cal, use_container_width=True)

st.divider()


# ════════════════════════════════════════════════════════════════════════════
# 6. Predicted probability distributions
# ════════════════════════════════════════════════════════════════════════════
st.subheader("📊 Predicted probability distribution")
st.caption("How the model distributes its confidence across all held-out matches.")

fig_dist = go.Figure()
for i, cls in enumerate(CLASS_LABELS):
    fig_dist.add_trace(go.Histogram(
        x=proba_test[:, i], name=cls,
        marker_color=CLASS_COLORS[i], opacity=0.7,
        nbinsx=20,
    ))
_plotly_layout(fig_dist, title="Distribution of predicted probabilities (WC 2022)",
               xaxis_title="Predicted probability",
               yaxis_title="Count", barmode="overlay", height=380)
st.plotly_chart(fig_dist, use_container_width=True)

st.divider()


# ════════════════════════════════════════════════════════════════════════════
# 7. Leave-one-tournament-out cross-validation
# ════════════════════════════════════════════════════════════════════════════
st.subheader("🔄 Leave-one-tournament-out cross-validation")
st.caption("Robustness check: each tournament is held out as the test fold in turn.")

loto_rows = []
for held in ALL_TOURNAMENTS:
    te = tour == held
    tr = ~te
    if te.sum() == 0 or tr.sum() == 0:
        continue
    m = MatchPredictor()
    m.train(X_all[tr], y_all[tr])
    ev = m.evaluate(X_all[te], y_all[te])
    base = MatchPredictor.baseline_accuracy(X_all[te], y_all[te])
    loto_rows.append({
        "Tournament": held, "Matches": int(te.sum()),
        "Accuracy": ev["accuracy"], "Baseline": base,
        "Edge": ev["accuracy"] - base,
        "Log Loss": ev["log_loss"], "Brier": ev["brier"],
    })

loto_df = pd.DataFrame(loto_rows)

col_loto_chart, col_loto_table = st.columns([1.2, 1])

with col_loto_chart:
    fig_loto = go.Figure()
    fig_loto.add_trace(go.Bar(
        name="Model", x=loto_df["Tournament"],
        y=loto_df["Accuracy"] * 100, marker_color=LIME,
    ))
    fig_loto.add_trace(go.Bar(
        name="FIFA baseline", x=loto_df["Tournament"],
        y=loto_df["Baseline"] * 100, marker_color=MUTED,
    ))
    _plotly_layout(fig_loto, title="Accuracy: model vs FIFA-rank baseline",
                   yaxis_title="Accuracy %", barmode="group", height=380)
    st.plotly_chart(fig_loto, use_container_width=True)

with col_loto_table:
    display_loto = loto_df.copy()
    display_loto["Accuracy"] = (display_loto["Accuracy"] * 100).round(1)
    display_loto["Baseline"] = (display_loto["Baseline"] * 100).round(1)
    display_loto["Edge"] = (display_loto["Edge"] * 100).round(1)
    display_loto["Log Loss"] = display_loto["Log Loss"].round(3)
    display_loto["Brier"] = display_loto["Brier"].round(3)
    st.dataframe(display_loto, hide_index=True, use_container_width=True)

    if len(loto_df):
        mean_acc = loto_df["Accuracy"].mean()
        mean_base = loto_df["Baseline"].mean()
        mean_edge = loto_df["Edge"].mean()
        st.markdown(f"""
        <div style="background:{PANEL};border-left:4px solid {LIME};border-radius:8px;
                    padding:.6rem .8rem;margin-top:.5rem;">
          <b style="color:{LIME}">Mean across folds:</b>
          <span style="color:{TEXT};font-size:.88rem">
            {mean_acc*100:.1f}% accuracy · {mean_base*100:.1f}% baseline ·
            <b>{mean_edge*100:+.1f} pts</b> edge
          </span>
        </div>
        """, unsafe_allow_html=True)

st.divider()


# ════════════════════════════════════════════════════════════════════════════
# 8. Feature correlation matrix
# ════════════════════════════════════════════════════════════════════════════
st.subheader("🔗 Feature correlation matrix")
st.caption("Pearson correlations between the six pre-match features. "
           "High correlation between features can cause multicollinearity.")

corr = X_all[FEATURE_COLUMNS].corr()
fig_corr = go.Figure(go.Heatmap(
    z=corr.values, x=FEATURE_COLUMNS, y=FEATURE_COLUMNS,
    colorscale=[[0, PURPLE], [0.5, BG], [1, LIME]],
    zmin=-1, zmax=1,
    text=corr.round(2).values, texttemplate="%{text}",
    textfont=dict(size=12, color=TEXT),
))
_plotly_layout(fig_corr, title="Feature correlations", height=420)
st.plotly_chart(fig_corr, use_container_width=True)

st.divider()


# ════════════════════════════════════════════════════════════════════════════
# 9. WC 2026 predictions overview
# ════════════════════════════════════════════════════════════════════════════
st.subheader("🌍 WC 2026 — model predictions overview")
st.caption("The trained model's predicted outcomes for all group-stage fixtures "
           "with known teams.")

try:
    wc26 = pd.read_sql("""
        SELECT m.fifa_match_num, m.stage,
               th.name AS home_team, ta.name AS away_team,
               m.status, m.home_score, m.away_score, m.winner
        FROM matches m
        JOIN teams th ON th.id = m.home_team_id
        JOIN teams ta ON ta.id = m.away_team_id
        WHERE m.tournament_label = 'WC 2026'
          AND m.stage = 'GROUP_STAGE'
        ORDER BY m.fifa_match_num
    """, engine)

    try:
        full_model = MatchPredictor.from_disk(MODEL_PATH)
    except Exception:
        full_model = model
    team_feats_sql = """
        SELECT t.name AS team, t.fifa_ranking,
               AVG(s.goals_scored - s.goals_conceded) AS form_goals,
               AVG(s.team_xg) AS avg_xg
        FROM teams t
        LEFT JOIN v_team_match_stats s ON s.team = t.name
        WHERE t.group_name IS NOT NULL
        GROUP BY t.name, t.fifa_ranking
    """
    team_meta = pd.read_sql(team_feats_sql, engine)
    tm = {r["team"]: r for _, r in team_meta.iterrows()}

    # NaN-safe: WC 2026 sides have no event-level form yet, so form_goals/avg_xg
    # come back NULL → NaN. `x or default` does NOT catch NaN (it's truthy), so
    # coerce explicitly to the neutral 0.0 the model was trained with.
    def _num(v, default=0.0):
        return default if v is None or pd.isna(v) else float(v)

    pred_rows = []
    for _, fx in wc26.iterrows():
        h, a = tm.get(fx["home_team"]), tm.get(fx["away_team"])
        if h is None or a is None:
            continue
        elo_h, elo_a = elo.rating(fx["home_team"]), elo.rating(fx["away_team"])
        features = {
            "elo_diff": elo_h - elo_a,
            "fifa_rank_gap": (_num(h.get("fifa_ranking"), 50) - _num(a.get("fifa_ranking"), 50)) * -1,
            "form_goals_diff": _num(h.get("form_goals")) - _num(a.get("form_goals")),
            "form_xg_diff": _num(h.get("avg_xg")) - _num(a.get("avg_xg")),
            "rest_days_diff": 0.0,
            "is_knockout": 0,
        }
        probs = full_model.predict_one(features)
        pick = max(probs, key=probs.get)
        pred_rows.append({
            "Match": f"{fx['home_team']} vs {fx['away_team']}",
            "Home Win %": round(probs["HOME_WIN"] * 100, 1),
            "Draw %": round(probs["DRAW"] * 100, 1),
            "Away Win %": round(probs["AWAY_WIN"] * 100, 1),
            "Prediction": fx["home_team"] if pick == "HOME_WIN"
                          else (fx["away_team"] if pick == "AWAY_WIN" else "Draw"),
            "Confidence": round(max(probs.values()) * 100, 1),
            "Status": fx["status"],
            "Actual": (f"{int(fx['home_score'])}–{int(fx['away_score'])}"
                       if fx["status"] == "FINISHED" else "—"),
        })

    pred_df = pd.DataFrame(pred_rows)
    st.dataframe(
        pred_df,
        hide_index=True, use_container_width=True,
        column_config={
            "Confidence": st.column_config.ProgressColumn(
                "Confidence", format="%.1f%%", min_value=0, max_value=100),
        },
    )

    finished = pred_df[pred_df["Status"] == "FINISHED"]
    if len(finished):
        st.markdown(f"**{len(finished)}** group-stage matches completed so far.")

except Exception as e:
    st.info(f"WC 2026 prediction table unavailable: {e}")


st.divider()


# ════════════════════════════════════════════════════════════════════════════
# 10. Methodology
# ════════════════════════════════════════════════════════════════════════════
with st.expander("ℹ️ Methodology — how to read this analysis"):
    st.markdown(f"""
**Model:** Multinomial logistic regression (3-class: Home Win / Draw / Away Win)
via scikit-learn, with a StandardScaler preprocessing step.

**Features (all leakage-free — known before kickoff):**
| Feature | Description |
|---------|-------------|
| `elo_diff` | Home Elo − Away Elo (from 92 years of WC history) |
| `fifa_rank_gap` | Away FIFA rank − Home FIFA rank (positive = home is better-ranked) |
| `form_goals_diff` | Rolling 5-match goal difference: home − away |
| `form_xg_diff` | Rolling 5-match xG difference: home − away |
| `rest_days_diff` | Days since last match: home − away |
| `is_knockout` | 1 if knockout stage, 0 if group stage |

**Validation strategy:**
- **Primary:** Strict temporal split — train on WC 2018 + EURO 2020, test on WC 2022
  (the model never sees any WC 2022 match during training)
- **Robustness:** Leave-one-tournament-out CV across 6 international tournaments

**Metrics explained:**
- **Log loss:** Penalises confident wrong predictions (lower = better)
- **Brier score:** Mean squared error of the probability vector (lower = better; 0.25 = coin flip)
- **Calibration:** Does a 70% confidence prediction come true ~70% of the time?

**Finance analogy:** This is point-in-time backtesting — every feature is the equivalent
of using only fundamentals that were public before the trade date. The model's edge over
the FIFA-rank baseline is its alpha.
""")

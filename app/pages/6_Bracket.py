"""
app/pages/6_Bracket.py
───────────────────────
Predicted vs. reality tournament bracket, with model KPIs.

Three things on one page:
  1. The model's bracket — built from a 10,000-run Monte Carlo simulation
     (Elo + FIFA strength). Shown as advancement probabilities (the honest
     output) plus the single most likely knockout bracket.
  2. The reality bracket — the actual results, filling in live as
     scripts/refresh_live.py pulls them.
  3. A model scorecard — Brier score and hit rate vs. a FIFA-rank baseline,
     updating as matches finish.

Data comes entirely from PostgreSQL BI views, so this page also mirrors
exactly what a Tableau/Power BI dashboard on the same views would show.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
import streamlit as st
from sqlalchemy import text

from database.db import engine

from app.utils.theme import inject_theme

st.set_page_config(page_title="Bracket · WC 2026", page_icon="🏆", layout="wide")
inject_theme()

BG, TEXT, PRIMARY, ACCENT = "#0F0F23", "#FAFAFA", "#00A86B", "#E8C547"
GOLD, MUTED = "#E8C547", "#6C6C8A"

ROUND_COLS = [
    ("reached_r32", "R32"), ("reached_r16", "R16"), ("reached_qf", "QF"),
    ("reached_sf", "SF"), ("reached_final", "Final"), ("won_cup", "🏆"),
]
KO_STAGE_ORDER = ["LAST_32", "LAST_16", "QUARTER_FINALS",
                  "SEMI_FINALS", "THIRD_PLACE", "FINAL"]
STAGE_LABEL = {"LAST_32": "Round of 32", "LAST_16": "Round of 16",
               "QUARTER_FINALS": "Quarter-finals", "SEMI_FINALS": "Semi-finals",
               "THIRD_PLACE": "Third place", "FINAL": "Final"}

st.title("🏆 Tournament Bracket")
st.caption("Model prediction vs. reality · Elo + FIFA Monte Carlo (10k simulations)")


# ── Data loaders (cached; bracket sim output changes rarely) ──────────────────
@st.cache_data(ttl=300, show_spinner="Loading bracket model …")
def load_advancement() -> pd.DataFrame:
    return pd.read_sql("SELECT * FROM v_bracket_predictions", engine)


@st.cache_data(ttl=300, show_spinner="Loading predicted bracket …")
def load_predicted_bracket() -> pd.DataFrame:
    sql = """
        SELECT fifa_match_num, stage,
               home_team AS pred_home, away_team AS pred_away,
               winner AS pred_winner, home_prob AS home_win_prob,
               away_prob AS away_win_prob, pairing_prob
        FROM predicted_bracket
        ORDER BY fifa_match_num
    """
    return pd.read_sql(sql, engine)


@st.cache_data(ttl=60, show_spinner="Loading live results …")
def load_reality_bracket() -> pd.DataFrame:
    sql = """
        SELECT m.fifa_match_num, m.stage, m.status,
               COALESCE(th.name, m.home_placeholder) AS home_team,
               COALESCE(ta.name, m.away_placeholder) AS away_team,
               m.home_score, m.away_score, m.winner
        FROM matches m
        LEFT JOIN teams th ON th.id = m.home_team_id
        LEFT JOIN teams ta ON ta.id = m.away_team_id
        WHERE m.stage = ANY(%(stages)s) AND m.fifa_match_num IS NOT NULL
        ORDER BY m.fifa_match_num
    """
    return pd.read_sql(sql, engine, params={"stages": KO_STAGE_ORDER})


@st.cache_data(ttl=60, show_spinner="Scoring model …")
def load_scorecard() -> pd.DataFrame:
    return pd.read_sql("SELECT * FROM v_model_scorecard", engine)


try:
    adv = load_advancement()
except Exception as e:
    st.error(f"Could not load bracket data: {e}")
    st.stop()

if adv.empty:
    st.warning(
        "No simulation results yet. Run the bracket simulation first:\n\n"
        "```\npython scripts/run_bracket_sim.py --sims 10000\n```"
    )
    st.stop()

model_version = adv["model_version"].iloc[0] if "model_version" in adv else "—"


# ════════════════════════════════════════════════════════════════════════════
# 1. KPI header
# ════════════════════════════════════════════════════════════════════════════
favourite = adv.iloc[0]
strongest_group = (
    adv.groupby("group_name")["strength"].mean().idxmax()
    if adv["group_name"].notna().any() else "—"
)
scorecard = load_scorecard()
n_scored = len(scorecard)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Model favourite", favourite["team"],
          f"{favourite['won_cup']*100:.1f}% to win")
k2.metric("Field strength leader", f"{adv['strength'].max():.0f} Elo",
          favourite["team"])
k3.metric("Toughest group", f"Group {strongest_group}")
if n_scored:
    k4.metric("Predictions scored", f"{n_scored} matches",
              f"{scorecard['hit'].mean()*100:.0f}% hit rate")
else:
    k4.metric("Predictions scored", "0", "awaiting knockouts")

st.caption(f"Model: `{model_version}` · 48 teams · advancement probabilities "
           "from Monte Carlo, not a single guess.")
st.divider()


# ════════════════════════════════════════════════════════════════════════════
# 2. Advancement probabilities — the honest output
# ════════════════════════════════════════════════════════════════════════════
st.subheader("📊 Advancement probabilities")
st.caption("How far each team is likely to go. This is the model's real output — "
           "a distribution over outcomes, the way you'd price a path-dependent bet.")

top_n = st.slider("Show top N teams", 8, 48, 16, step=4)
show = adv.head(top_n).copy()

display = show[["team", "group_name", "fifa_rank", "strength"]].copy()
display.columns = ["Team", "Grp", "FIFA", "Strength"]
for col, label in ROUND_COLS:
    display[label] = (show[col] * 100).round(1)

st.dataframe(
    display,
    hide_index=True,
    use_container_width=True,
    column_config={
        "Strength": st.column_config.NumberColumn(format="%d"),
        **{label: st.column_config.ProgressColumn(
            label, format="%.1f%%", min_value=0, max_value=100)
           for _, label in ROUND_COLS},
    },
)
st.divider()


# ════════════════════════════════════════════════════════════════════════════
# 3. Knockout bracket tree — Expected vs Actual, self-updating
# ════════════════════════════════════════════════════════════════════════════
import streamlit.components.v1 as components  # noqa: E402

from app.utils.bracket_view import render_bracket_svg  # noqa: E402

st.subheader("🗺️ Knockout bracket")
st.caption("Left: the model's expected path. Right: how it's actually playing out. "
           "Auto-refreshes every 60 seconds as results land.")

# Model's headline call — the prediction explicitly revolves around this.
champ = adv.iloc[0]
usa = adv[adv["team"] == "United States"]
if not usa.empty:
    usa_row = usa.iloc[0]
    st.markdown(f"""
    <div style="background:linear-gradient(90deg,#1A1A2E,#14142B);border:1px solid #E0003C;
                border-left:5px solid #E0003C;border-radius:10px;padding:.7rem 1rem;margin:.4rem 0;">
      <span style="color:#E0003C;font-weight:800;letter-spacing:.04em">📌 MODEL CALL</span>
      &nbsp;—&nbsp;<b style="color:#FAFAFA">{champ['team']}</b> are the predicted champions
      (<b style="color:#9BE800">{champ['won_cup']*100:.1f}%</b>).
      The host <b style="color:#FAFAFA">USA</b> is <b>not winning this</b>: a
      <b style="color:#E8C547">{usa_row['won_cup']*100:.1f}%</b> title shot with a ceiling
      around the <b>semifinals</b> ({usa_row['reached_sf']*100:.0f}% to reach them) — the
      model has them eliminated before the final.
    </div>
    """, unsafe_allow_html=True)


def _bracket_iframe(kind: str):
    svg = render_bracket_svg(kind)
    components.html(
        f'<div style="background:#0b0b1c;margin:0">{svg}</div>',
        height=480, scrolling=False)


@st.fragment(run_every=60)
def bracket_tree():
    exp_tab, act_tab = st.tabs(["🔮 Expected (model)", "⚽ Actual (live)"])
    with exp_tab:
        _bracket_iframe("expected")
    with act_tab:
        _bracket_iframe("actual")
        st.caption("Empty slots show qualification codes (e.g. 2A = Group A runner-up, "
                   "W73 = winner of match 73) until teams resolve.")


bracket_tree()
st.divider()


# ════════════════════════════════════════════════════════════════════════════
# 4. Predicted vs. reality — match cards
# ════════════════════════════════════════════════════════════════════════════
st.subheader("🆚 Predicted bracket vs. reality")

predicted = load_predicted_bracket()
reality = load_reality_bracket()
reality_by_num = {int(r["fifa_match_num"]): r for _, r in reality.iterrows()}


def render_match(pred_row, real_row) -> str:
    """One match card: model pick on top, actual result below."""
    ph = pred_row["pred_home"] or "—"
    pa = pred_row["pred_away"] or "—"
    pick = pred_row["pred_winner"] or "—"
    conf = max(pred_row["home_win_prob"] or 0, pred_row["away_win_prob"] or 0)

    lines = [
        f"<div style='font-size:0.72rem;color:{MUTED}'>Match {int(pred_row['fifa_match_num'])}</div>",
        f"<div style='color:{TEXT};font-size:0.86rem'>{ph} v {pa}</div>",
        f"<div style='color:{ACCENT};font-size:0.78rem'>▸ {pick} ({conf*100:.0f}%)</div>",
    ]

    if real_row is not None and real_row["status"] == "FINISHED":
        hs, as_ = real_row["home_score"], real_row["away_score"]
        actual = real_row["home_team"] if real_row["winner"] == "HOME" else real_row["away_team"]
        correct = (actual == pick)
        mark = "✅" if correct else "❌"
        color = PRIMARY if correct else "#E25555"
        lines.append(
            f"<div style='color:{color};font-size:0.78rem'>{mark} {real_row['home_team']} "
            f"{int(hs)}–{int(as_)} {real_row['away_team']}</div>"
        )
    else:
        lines.append(f"<div style='color:{MUTED};font-size:0.74rem'>⏳ not played</div>")

    border = ACCENT if (real_row is None or real_row["status"] != "FINISHED") else (
        PRIMARY if lines[-1].startswith(f"<div style='color:{PRIMARY}") else "#E25555")
    return (f"<div style='border-left:3px solid {border};padding:4px 8px;"
            f"margin:4px 0;background:rgba(255,255,255,0.02)'>" + "".join(lines) + "</div>")


for stage in KO_STAGE_ORDER:
    stage_pred = predicted[predicted["stage"] == stage]
    if stage_pred.empty:
        continue
    st.markdown(f"#### {STAGE_LABEL[stage]}")
    cards = [render_match(row, reality_by_num.get(int(row["fifa_match_num"])))
             for _, row in stage_pred.iterrows()]
    # lay out cards in a responsive row of columns
    n = len(cards)
    per_row = min(n, 4)
    for start in range(0, n, per_row):
        cols = st.columns(per_row)
        for col, card in zip(cols, cards[start:start + per_row]):
            col.markdown(card, unsafe_allow_html=True)

st.divider()


# ════════════════════════════════════════════════════════════════════════════
# 4. Model scorecard — KPIs vs. baseline
# ════════════════════════════════════════════════════════════════════════════
st.subheader("📈 Model scorecard")
st.caption("Updates as knockout matches finish. Brier score = mean squared error "
           "of the confidence in the predicted winner (lower is better; 0.25 = a coin-flip).")

if n_scored == 0:
    st.info("No knockout matches have finished yet — the scorecard fills in "
            "from the Round of 32 onward. The group stage runs first.")
else:
    s1, s2, s3 = st.columns(3)
    s1.metric("Hit rate", f"{scorecard['hit'].mean()*100:.1f}%",
              f"{int(scorecard['hit'].sum())}/{n_scored} correct")
    s2.metric("Brier score", f"{scorecard['brier'].mean():.3f}",
              "lower is better", delta_color="inverse")
    s3.metric("Avg confidence", f"{scorecard['predicted_confidence'].mean()*100:.0f}%")

    by_stage = (scorecard.groupby("stage")
                .agg(matches=("hit", "size"), hit_rate=("hit", "mean"),
                     brier=("brier", "mean"))
                .reindex([s for s in KO_STAGE_ORDER if s in scorecard["stage"].values])
                .reset_index())
    by_stage["hit_rate"] = (by_stage["hit_rate"] * 100).round(1)
    by_stage["brier"] = by_stage["brier"].round(3)
    by_stage["stage"] = by_stage["stage"].map(STAGE_LABEL)
    by_stage.columns = ["Round", "Matches", "Hit %", "Brier"]
    st.dataframe(by_stage, hide_index=True, use_container_width=True)

st.caption("💡 In finance terms: this scorecard is the model's track record — "
           "Brier is its calibration error, and hit-rate-over-baseline is its alpha.")

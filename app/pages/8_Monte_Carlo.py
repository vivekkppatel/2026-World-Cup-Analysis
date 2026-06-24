"""
app/pages/8_Monte_Carlo.py
────────────────────────────
Interactive Monte Carlo simulation of the World Cup 2026.

Runs the real tournament simulator (Elo + FIFA strength → Poisson scorelines)
live: pick a number of simulations and watch the advancement distribution form.
Also surfaces the canonical 10,000-run result stored in the database so the
page is useful before you press Run.

Quant-finance analog: each simulated tournament is one price path; advancement
probabilities are the distribution of outcomes across paths — exactly how you'd
price a path-dependent option or estimate VaR instead of trusting one forecast.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.utils.theme import inject_theme
from database.db import engine, health_check
from models.tournament_sim import TournamentSimulator

st.set_page_config(page_title="Monte Carlo · WC 2026", page_icon="🎲", layout="wide")
inject_theme()

BG, PANEL, TEXT = "#0F0F23", "#1A1A2E", "#FAFAFA"
PRIMARY, ACCENT, PURPLE, LIME, MUTED = "#00A86B", "#E8C547", "#6D28D9", "#9BE800", "#8B8FA8"

ROUND_COLS = [
    ("reached_r32", "R32"), ("reached_r16", "R16"), ("reached_qf", "QF"),
    ("reached_sf", "SF"), ("reached_final", "Final"), ("won_cup", "🏆"),
]

st.title("🎲 Monte Carlo Simulation")
st.caption("Run the WC 2026 tournament thousands of times · advancement is a "
           "distribution over outcomes, not a single guessed bracket")


def _layout(fig: go.Figure, **kw) -> go.Figure:
    fig.update_layout(plot_bgcolor=BG, paper_bgcolor=BG, font_color=TEXT,
                      margin=dict(l=40, r=30, t=50, b=40),
                      legend=dict(bgcolor="rgba(0,0,0,0)", font_color=TEXT), **kw)
    return fig


@st.cache_resource(show_spinner="Loading team strengths & bracket structure …")
def load_inputs():
    """Elo+FIFA+form strengths and the KO structure — cached so only the
    simulation itself re-runs when the slider changes."""
    from scripts.run_bracket_sim import load_strengths, load_bracket_structure
    groups, strengths = load_strengths()
    structure = load_bracket_structure()
    return groups, structure, strengths


@st.cache_data(ttl=300, show_spinner="Loading stored 10k-run result …")
def load_stored() -> pd.DataFrame:
    return pd.read_sql("SELECT * FROM v_bracket_predictions", engine)


if not health_check():
    st.error("Cannot connect to database. Check DATABASE_URL in .env")
    st.stop()


def advancement_df(rows: list[dict], strengths: dict | None = None) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if strengths is not None and "team" in df:
        df["strength"] = df["team"].map(lambda t: round(strengths.get(t, 1500), 0))
    return df.sort_values("won_cup", ascending=False).reset_index(drop=True)


def champion_bar(df: pd.DataFrame, n: int = 16) -> go.Figure:
    top = df.head(n).sort_values("won_cup")
    fig = go.Figure(go.Bar(
        y=top["team"], x=(top["won_cup"] * 100).round(1), orientation="h",
        marker=dict(color=(top["won_cup"] * 100),
                    colorscale=[[0, PURPLE], [0.5, PRIMARY], [1, LIME]]),
        text=[f"{v:.1f}%" for v in (top["won_cup"] * 100)], textposition="outside",
    ))
    return _layout(fig, title="Title odds — P(win the cup)", height=max(320, n * 26),
                   xaxis_title="Champion probability %")


def funnel_heatmap(df: pd.DataFrame, n: int = 16) -> go.Figure:
    top = df.head(n)
    z = [[row[col] * 100 for col, _ in ROUND_COLS] for _, row in top.iterrows()]
    fig = go.Figure(go.Heatmap(
        z=z, x=[lbl for _, lbl in ROUND_COLS], y=top["team"],
        colorscale=[[0, "#14142B"], [1, LIME]], reversescale=False,
        text=[[f"{v:.0f}" for v in r] for r in z], texttemplate="%{text}",
        textfont=dict(size=10, color=TEXT), showscale=True,
        hovertemplate="%{y} · %{x}: %{z:.1f}%<extra></extra>",
    ))
    fig.update_yaxes(autorange="reversed")
    return _layout(fig, title="Advancement funnel — P(reach each round) %",
                   height=max(360, n * 26))


# ════════════════════════════════════════════════════════════════════════════
# Interactive live simulation
# ════════════════════════════════════════════════════════════════════════════
st.subheader("▶️ Run a live simulation")
c1, c2 = st.columns([3, 1])
with c1:
    n_sims = st.slider("Number of simulations", 500, 20000, 5000, step=500,
                       help="More simulations → tighter probability estimates "
                            "(Monte Carlo standard error shrinks ~1/√N).")
with c2:
    st.write("")
    st.write("")
    run = st.button("🎲 Run simulation", type="primary", use_container_width=True)

if run:
    try:
        groups, structure, strengths = load_inputs()
        if not structure.matches:
            st.error("No knockout structure found. Run scripts/refresh_live.py first.")
            st.stop()
        with st.spinner(f"Simulating {n_sims:,} tournaments …"):
            sim = TournamentSimulator(groups, structure)
            result = sim.run(n_sims, seed=2026)
        st.session_state["mc_df"] = advancement_df(result.advancement_table(), strengths)
        st.session_state["mc_n"] = n_sims
    except Exception as e:
        st.error(f"Simulation failed: {e}")

if "mc_df" in st.session_state:
    df = st.session_state["mc_df"]
    n = st.session_state.get("mc_n", n_sims)
    champ = df.iloc[0]
    strongest = df.loc[df["strength"].idxmax()] if "strength" in df else champ

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Predicted champion", champ["team"], f"{champ['won_cup']*100:.1f}% to win")
    k2.metric("Simulations", f"{n:,}")
    k3.metric("Strength leader", f"{strongest.get('strength', 0):.0f} Elo", strongest["team"])
    se = (champ["won_cup"] * (1 - champ["won_cup"]) / n) ** 0.5 * 100
    k4.metric("Champion ± std err", f"±{se:.2f} pts", "shrinks with more sims")

    top_n = st.slider("Show top N teams", 8, 48, 16, step=4, key="live_top")
    cc1, cc2 = st.columns([1, 1.3])
    with cc1:
        st.plotly_chart(champion_bar(df, top_n), use_container_width=True)
    with cc2:
        st.plotly_chart(funnel_heatmap(df, top_n), use_container_width=True)

    st.markdown("##### Per-round probabilities (live run)")
    disp = df.head(top_n)[["team"] + [c for c, _ in ROUND_COLS]].copy()
    disp.columns = ["Team"] + [lbl for _, lbl in ROUND_COLS]
    for _, lbl in ROUND_COLS:
        disp[lbl] = (disp[lbl] * 100).round(1)
    st.dataframe(disp, hide_index=True, use_container_width=True, column_config={
        lbl: st.column_config.ProgressColumn(lbl, format="%.1f%%", min_value=0, max_value=100)
        for _, lbl in ROUND_COLS})
    st.caption("💡 More simulations tighten every estimate — the champion standard error "
               "above scales with 1/√N, so 4× the sims halves the noise.")
else:
    st.info("Press **Run simulation** to play out the tournament live. "
            "The canonical 10,000-run result is shown below in the meantime.")

st.divider()

# ════════════════════════════════════════════════════════════════════════════
# Canonical stored result (daily 10k-run pipeline)
# ════════════════════════════════════════════════════════════════════════════
st.subheader("🗄️ Canonical 10,000-run result")
st.caption("Written daily by the GitHub Actions pipeline (scripts/run_bracket_sim.py "
           "--sims 10000) and read straight from the database.")

stored = load_stored()
if stored.empty:
    st.info("No stored simulation yet — the daily pipeline populates this. "
            "Run a live simulation above in the meantime.")
else:
    stored = stored.sort_values("won_cup", ascending=False).reset_index(drop=True)
    mv = stored["model_version"].iloc[0] if "model_version" in stored else "—"
    favourite = stored.iloc[0]
    s1, s2, s3 = st.columns(3)
    s1.metric("Model favourite", favourite["team"], f"{favourite['won_cup']*100:.1f}% to win")
    s2.metric("Field strength leader", f"{stored['strength'].max():.0f} Elo")
    s3.metric("Model", mv)

    g1, g2 = st.columns([1, 1.3])
    with g1:
        st.plotly_chart(champion_bar(stored, 16), use_container_width=True)
    with g2:
        st.plotly_chart(funnel_heatmap(stored, 16), use_container_width=True)

    top_n2 = st.slider("Show top N teams", 8, 48, 16, step=4, key="stored_top")
    disp2 = stored.head(top_n2)[["team", "group_name", "fifa_rank", "strength"]
                                + [c for c, _ in ROUND_COLS]].copy()
    disp2.columns = ["Team", "Grp", "FIFA", "Strength"] + [lbl for _, lbl in ROUND_COLS]
    for _, lbl in ROUND_COLS:
        disp2[lbl] = (disp2[lbl] * 100).round(1)
    st.dataframe(disp2, hide_index=True, use_container_width=True, column_config={
        "Strength": st.column_config.NumberColumn(format="%d"),
        **{lbl: st.column_config.ProgressColumn(lbl, format="%.1f%%", min_value=0, max_value=100)
           for _, lbl in ROUND_COLS}})

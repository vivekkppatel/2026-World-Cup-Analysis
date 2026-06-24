"""
app/main.py
────────────
Streamlit home page — World Cup 2026 Analytics Platform.

FIFA-26-inspired animated hero (geometric color blocks, giant "26",
orbiting ball, host-city marquee) over live database-driven KPIs.
Run with: streamlit run app/main.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import streamlit as st

from app.utils.theme import inject_theme

st.set_page_config(
    page_title="WC 2026 Analytics",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_theme()

HOST_CITIES = [
    "Mexico City", "Guadalajara", "Monterrey", "Toronto", "Vancouver",
    "Seattle", "San Francisco", "Los Angeles", "Kansas City", "Dallas",
    "Houston", "Atlanta", "Miami", "Boston", "Philadelphia", "New York",
]


# ── Live data (graceful fallbacks — page must render with an empty DB) ───────
@st.cache_data(ttl=300, show_spinner=False)
def load_pulse() -> dict:
    out = {"played": 0, "favourite": None, "fav_prob": None,
           "next_fixture": None, "goals": 0}
    try:
        from database.db import engine
        res = pd.read_sql(
            "SELECT COUNT(*) n, COALESCE(SUM(home_score+away_score),0) g "
            "FROM matches WHERE tournament_label='WC 2026' AND status='FINISHED'",
            engine)
        out["played"], out["goals"] = int(res["n"][0]), int(res["g"][0])

        fav = pd.read_sql(
            "SELECT team, won_cup FROM v_bracket_predictions LIMIT 1", engine)
        if not fav.empty:
            out["favourite"] = fav["team"][0]
            out["fav_prob"] = float(fav["won_cup"][0])

        nxt = pd.read_sql(
            "SELECT home_team, away_team, kickoff_utc, venue "
            "FROM v_upcoming_fixtures LIMIT 1", engine)
        if not nxt.empty:
            out["next_fixture"] = nxt.iloc[0].to_dict()
    except Exception:
        pass
    return out


pulse = load_pulse()

# ── Hero ──────────────────────────────────────────────────────────────────────
marquee_items = " · ".join(HOST_CITIES)
st.markdown(f"""
<style>
.wc-hero {{
    position: relative;
    border-radius: 20px;
    overflow: hidden;
    background: #0B0B1C;
    min-height: 380px;
    margin-bottom: .75rem;
    border: 1px solid #2D2D4E;
}}
/* FIFA-26 geometric color field */
.wc-hero .blk {{ position: absolute; will-change: transform; }}
.blk-purple {{
    width: 46%; height: 130%; left: -8%; top: -15%;
    background: linear-gradient(160deg, #7C3AED, #5B21B6);
    border-radius: 0 38% 42% 0;
    animation: wcDrift 11s ease-in-out infinite alternate;
}}
.blk-red {{
    width: 42%; height: 150%; right: 14%; top: -25%;
    background: linear-gradient(200deg, #FF1F4E, #C40031);
    border-radius: 46% 0 0 44%;
    transform: rotate(8deg);
    animation: wcDrift 13s ease-in-out infinite alternate-reverse;
}}
.blk-lime {{
    width: 26%; height: 120%; right: -6%; top: -10%;
    background: linear-gradient(180deg, #B4FF1A, #7ACC00);
    border-radius: 50% 0 0 30%;
    animation: wcDrift 9s ease-in-out infinite alternate;
}}
.blk-glow {{
    width: 60%; height: 60%; left: 20%; top: 20%;
    background: radial-gradient(closest-side, rgba(232,197,71,.18), transparent);
    animation: wcPulse 6s ease-in-out infinite;
}}
.wc-hero .inner {{
    position: relative; z-index: 2;
    padding: 2.6rem 3rem 4.4rem 3rem;
}}
.wc-kicker {{
    font-family: 'Inter', sans-serif; font-weight: 800;
    font-size: .8rem; letter-spacing: .32em; color: #E8C547;
    text-transform: uppercase;
    animation: wcRise .6s .05s cubic-bezier(.16,1,.3,1) both;
}}
.wc-title {{
    font-family: 'Archivo Black', sans-serif;
    font-size: clamp(2.6rem, 6vw, 4.6rem);
    line-height: 1.02; color: #FFFFFF; margin: .4rem 0 .2rem 0;
    text-shadow: 0 8px 40px rgba(0,0,0,.55);
    animation: wcRise .6s .15s cubic-bezier(.16,1,.3,1) both;
}}
.wc-title .two6 {{
    color: #FFFFFF;
    background: linear-gradient(135deg, #FFFFFF 35%, #E8C547 75%);
    -webkit-background-clip: text; background-clip: text;
    -webkit-text-fill-color: transparent;
}}
.wc-ball {{
    display: inline-block; font-size: clamp(2rem, 4vw, 3.2rem);
    margin-left: .6rem; vertical-align: middle;
    animation: wcSpin 7s linear infinite, wcBounce 2.6s ease-in-out infinite;
}}
.wc-sub {{
    color: #D9DBEC; font-size: 1.02rem; max-width: 46rem;
    animation: wcRise .6s .28s cubic-bezier(.16,1,.3,1) both;
}}
.wc-chips {{ margin-top: 1.1rem; animation: wcRise .6s .4s cubic-bezier(.16,1,.3,1) both; }}
.wc-chip {{
    display: inline-block; margin: 0 .45rem .45rem 0;
    padding: .38rem .85rem; border-radius: 999px;
    font-weight: 800; font-size: .82rem; letter-spacing: .06em;
    background: rgba(255,255,255,.10); color: #FFFFFF;
    border: 1px solid rgba(255,255,255,.22);
    backdrop-filter: blur(6px);
    transition: transform .2s ease, background .2s ease;
}}
.wc-chip:hover {{ transform: translateY(-2px) scale(1.04); background: rgba(255,255,255,.18); }}
/* Host-city marquee */
.wc-marquee {{
    position: absolute; bottom: 0; left: 0; right: 0; z-index: 2;
    background: rgba(10,10,25,.66); backdrop-filter: blur(8px);
    border-top: 1px solid rgba(255,255,255,.12);
    overflow: hidden; white-space: nowrap; padding: .5rem 0;
}}
.wc-marquee .track {{
    display: inline-block; white-space: nowrap;
    font-weight: 800; font-size: .8rem; letter-spacing: .22em;
    color: #B4FF1A; text-transform: uppercase;
    animation: wcMarquee 38s linear infinite;
}}
@keyframes wcDrift   {{ from {{ transform: translateY(-1.5%) rotate(0deg); }}
                        to   {{ transform: translateY(2.5%) rotate(2deg); }} }}
@keyframes wcPulse   {{ 0%,100% {{ transform: scale(1); opacity:.8; }}
                        50%     {{ transform: scale(1.12); opacity:1; }} }}
@keyframes wcRise    {{ from {{ opacity: 0; transform: translateY(22px); }}
                        to   {{ opacity: 1; transform: translateY(0); }} }}
@keyframes wcSpin    {{ from {{ transform: rotate(0); }} to {{ transform: rotate(360deg); }} }}
@keyframes wcBounce  {{ 0%,100% {{ translate: 0 0; }} 50% {{ translate: 0 -10px; }} }}
@keyframes wcMarquee {{ from {{ transform: translateX(0); }} to {{ transform: translateX(-50%); }} }}
</style>

<div class="wc-hero">
  <div class="blk blk-purple"></div>
  <div class="blk blk-red"></div>
  <div class="blk blk-lime"></div>
  <div class="blk blk-glow"></div>
  <div class="inner">
    <div class="wc-kicker">FIFA World Cup · United States · Canada · Mexico</div>
    <div class="wc-title">WORLD CUP <span class="two6">26</span><span class="wc-ball">⚽</span></div>
    <p class="wc-sub">An end-to-end analytics platform — 9 tournaments of data,
    a leakage-free ML match model, a 10,000-run Monte Carlo bracket, and
    live model-vs-reality KPIs as the tournament unfolds.</p>
    <div class="wc-chips">
      <span class="wc-chip">48 TEAMS</span>
      <span class="wc-chip">104 MATCHES</span>
      <span class="wc-chip">16 HOST CITIES</span>
      <span class="wc-chip">12 GROUPS</span>
      <span class="wc-chip">39 DAYS</span>
    </div>
  </div>
  <div class="wc-marquee"><span class="track">{marquee_items} · {marquee_items} · </span></div>
</div>
""", unsafe_allow_html=True)

# ── Live pulse (2×2 so long team names don't truncate on narrow windows) ─────
r1c1, r1c2 = st.columns(2)
r1c1.metric("Matches Played", pulse["played"], f"{104 - pulse['played']} remaining")
r1c2.metric("Goals So Far", pulse["goals"])

r2c1, r2c2 = st.columns(2)
if pulse["favourite"]:
    r2c1.metric("Model Favourite 🏆", pulse["favourite"],
                f"{pulse['fav_prob']*100:.1f}% to win" if pulse["fav_prob"] else None)
else:
    r2c1.metric("Model Favourite 🏆", "—", "run the simulation")
if pulse["next_fixture"]:
    nf = pulse["next_fixture"]
    when = pd.to_datetime(nf["kickoff_utc"]).strftime("%b %d · %H:%M UTC")
    r2c2.metric("Next Match ⚽", f"{nf['home_team']} v {nf['away_team']}", when)
else:
    r2c2.metric("Next Match ⚽", "—")

st.divider()

# ── Explore ───────────────────────────────────────────────────────────────────
st.subheader("Explore the platform")
# Paths are relative to the entrypoint file (app/main.py), per st.page_link.
PAGES = [
    ("pages/1_Tournament_Overview.py", "🌍", "Tournament Overview",
     "Live standings, scorers & fixtures"),
    ("pages/2_Team_Analysis.py", "🔵", "Team Analysis",
     "xG timelines & head-to-head, 6 tournaments"),
    ("pages/3_Player_Stats.py", "👤", "Player Stats",
     "Per-90 leaderboards & percentile radars"),
    ("pages/4_Match_Predictor.py", "🔮", "Match Predictor",
     "Leakage-free ML win probabilities"),
    ("pages/5_Player_Valuation.py", "💰", "Player Valuation",
     "CPCS scoring — find undervalued players"),
    ("pages/6_Bracket.py", "🏆", "Bracket",
     "Predicted vs reality, with model KPIs"),
    ("pages/7_Regression_Analysis.py", "📊", "Regression Analysis",
     "Coefficients, calibration & cross-validation"),
    ("pages/8_Monte_Carlo.py", "🎲", "Monte Carlo",
     "Live 10k-run tournament simulation"),
]
rows = [PAGES[:3], PAGES[3:]]
for row in rows:
    cols = st.columns(len(row))
    for col, (path, icon, label, desc) in zip(cols, row):
        with col:
            st.page_link(path, label=f"{label} — {desc}", icon=icon,
                         use_container_width=True)

st.divider()

# ── Status footer ─────────────────────────────────────────────────────────────
s1, s2 = st.columns(2)
with s1:
    try:
        from database.db import health_check
        if health_check():
            st.success("✅ PostgreSQL connected — 9 tournaments loaded")
        else:
            st.error("❌ Database not connected — check DATABASE_URL in .env")
    except Exception:
        st.warning("⚠️ Run `python scripts/seed_db.py` to initialize the database")
with s2:
    st.info("📈 BI views power Tableau & Power BI too — see docs/BI_SETUP.md")

st.caption("StatsBomb Open Data · football-data.org · openfootball · Fjelstul WC Database "
           "· Portfolio project by Vivek Patel · Class of 2028")

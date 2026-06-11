"""
app/main.py
────────────
Streamlit home page — World Cup 2026 Analytics Platform.
Run with: streamlit run app/main.py
"""
import sys
from pathlib import Path

# Make project root importable
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="WC 2026 Analytics",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Dark background */
    .stApp { background-color: #0F0F23; }
    .main .block-container { padding-top: 1.5rem; }

    /* Metric cards */
    [data-testid="metric-container"] {
        background-color: #1A1A2E;
        border: 1px solid #2D2D4E;
        border-radius: 8px;
        padding: 12px;
    }
    [data-testid="metric-container"] label { color: #8B8FA8 !important; }
    [data-testid="metric-container"] [data-testid="stMetricValue"] {
        color: #FAFAFA !important; font-size: 1.6rem !important;
    }

    /* Sidebar */
    [data-testid="stSidebar"] { background-color: #1A1A2E; }

    /* Headers */
    h1, h2, h3 { color: #FAFAFA; }

    /* DataFrames */
    .dataframe { background-color: #1A1A2E !important; color: #FAFAFA !important; }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
col_flag, col_title = st.columns([1, 8])
with col_flag:
    st.markdown("## ⚽")
with col_title:
    st.markdown("# World Cup 2026 Analytics Platform")
    st.caption("Real-time tournament intelligence · USA · Canada · Mexico")

st.divider()

# ── Tournament at a glance ────────────────────────────────────────────────────
st.subheader("📊 Tournament at a Glance")

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Teams", "48")
col2.metric("Groups", "12")
col3.metric("Total Matches", "104")
col4.metric("Host Cities", "16")
col5.metric("Tournament Days", "39")

st.divider()

# ── Navigation guide ──────────────────────────────────────────────────────────
st.subheader("🗺️ Explore the Dashboard")

nav_cols = st.columns(3)

with nav_cols[0]:
    st.markdown("""
    **🌍 Tournament Overview**
    Live group standings, top scorers,
    and latest match results.
    """)
    st.markdown("""
    **🔵 Team Analysis**
    Passing networks, xG timelines,
    and formation deep-dives per team.
    """)

with nav_cols[1]:
    st.markdown("""
    **👤 Player Stats**
    Per-90 leaderboards with radar
    charts for player comparisons.
    """)
    st.markdown("""
    **🔮 Match Predictor**
    Win probability model trained on
    WC 2018 + 2022 StatsBomb data.
    """)

with nav_cols[2]:
    st.markdown("""
    **💰 Player Valuation**
    Composite contribution scoring —
    find undervalued players by position.
    """)

st.divider()

# ── Data status ───────────────────────────────────────────────────────────────
st.subheader("🔌 Data Source Status")
status_cols = st.columns(2)

with status_cols[0]:
    st.markdown("**Live Data (football-data.org)**")
    try:
        from database.db import health_check
        db_ok = health_check()
        st.success("✅ Database connected") if db_ok else st.error("❌ Database not connected")
    except Exception:
        st.warning("⚠️ Run `python scripts/seed_db.py` to initialize the database")

with status_cols[1]:
    st.markdown("**Historical Data (StatsBomb)**")
    try:
        from statsbombpy import sb
        comps = sb.competitions()
        wc_available = any((comps["competition_id"] == 43).values)
        st.success("✅ StatsBomb data available") if wc_available else st.warning("⚠️ StatsBomb data not loaded")
    except Exception:
        st.warning("⚠️ Run `pip install statsbombpy` to enable historical analysis")

st.divider()
st.caption("Built with StatsBomb Open Data & football-data.org · Portfolio project by Vivek Patel · Class of 2028")

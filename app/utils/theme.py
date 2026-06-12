"""
app/utils/theme.py
───────────────────
Shared visual identity for every page: FIFA-26-inspired palette, motion
design, and the hover-reveal sidebar navigation.

Call `inject_theme()` immediately after st.set_page_config() on each page.
All animations use compositor-friendly properties (transform/opacity) and
are disabled for users with prefers-reduced-motion.

Palette (from the FIFA 26 brand language):
    ink      #0F0F23   deep navy base
    panel    #1A1A2E   raised surfaces
    purple   #6D28D9   brand block
    red      #E0003C   brand block
    lime     #9BE800   brand block
    green    #00A86B   pitch green (primary actions)
    gold     #E8C547   trophy accent
"""
import streamlit as st

# Page order in the sidebar nav is fixed (main + numbered pages), which lets
# pure CSS attach a hover-revealed description to each item via nth-child.
_NAV_ITEMS = [
    ("🏠 Home", "Mission control · WC 2026"),
    ("🌍 Tournament Overview", "Standings · scorers · fixtures"),
    ("🔵 Team Analysis", "xG timelines · head-to-head"),
    ("👤 Player Stats", "Per-90 leaderboards · radars"),
    ("🔮 Match Predictor", "ML win probabilities"),
    ("💰 Player Valuation", "CPCS · undervalued XI"),
    ("🏆 Bracket", "Predicted vs reality · KPIs"),
]


def _nav_css() -> str:
    """Per-item sidebar rules: relabel Home, add hover-revealed subtitles."""
    rules = []
    for i, (label, desc) in enumerate(_NAV_ITEMS, start=1):
        # Hover-revealed subtitle under each nav label
        rules.append(f"""
        [data-testid="stSidebarNav"] li:nth-child({i}) a::after {{
            content: "{desc}";
            display: block;
            font-size: 0.68rem;
            font-weight: 400;
            letter-spacing: 0.04em;
            color: #9BE800;
            max-height: 0;
            opacity: 0;
            overflow: hidden;
            transform: translateY(-4px);
            transition: max-height .25s ease, opacity .25s ease, transform .25s ease;
        }}
        [data-testid="stSidebarNav"] li:nth-child({i}) a:hover::after {{
            max-height: 1.2rem;
            opacity: 1;
            transform: translateY(0);
        }}""")
    # The first item is the bare filename ("main") — relabel it via CSS.
    rules.append("""
        [data-testid="stSidebarNav"] li:nth-child(1) a span {
            font-size: 0 !important;
        }
        [data-testid="stSidebarNav"] li:nth-child(1) a span::before {
            content: "🏠 Home";
            font-size: 0.95rem;
        }""")
    return "\n".join(rules)


def inject_theme() -> None:
    """Inject the global stylesheet. Idempotent per rerun."""
    st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Archivo+Black&family=Inter:wght@400;600;800&display=swap');

/* ── Base ─────────────────────────────────────────────────────────────── */
.stApp {{ background-color: #0F0F23; }}
html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}
h1, h2 {{ font-family: 'Archivo Black', 'Inter', sans-serif !important;
          letter-spacing: -0.01em; color: #FAFAFA; }}
h3 {{ color: #FAFAFA; }}

/* Animated gradient underline on section headers */
h2 {{ position: relative; padding-bottom: .25rem; }}
h2::after {{
    content: ""; position: absolute; left: 0; bottom: 0;
    width: 64px; height: 4px; border-radius: 2px;
    background: linear-gradient(90deg, #6D28D9, #E0003C, #9BE800);
    background-size: 200% 100%;
    animation: wcSlideGradient 4s linear infinite;
}}

/* ── Page-load transition (replays on every page switch) ─────────────── */
.main .block-container,
[data-testid="stAppViewContainer"] .block-container {{
    padding-top: 1.2rem;
    animation: wcPageIn .55s cubic-bezier(.16, 1, .3, 1) both;
}}

/* ── Sidebar ──────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {{
    background: linear-gradient(180deg, #14142B 0%, #1A1A2E 100%);
    border-right: 1px solid #2D2D4E;
}}
[data-testid="stSidebarNav"]::before {{
    content: "⚽ WC26 ANALYTICS";
    display: block;
    font-family: 'Archivo Black', sans-serif;
    font-size: 0.9rem;
    letter-spacing: 0.14em;
    color: #FAFAFA;
    padding: 1rem 1.1rem .6rem 1.1rem;
}}
[data-testid="stSidebarNav"] ul {{ padding-top: .2rem; }}
[data-testid="stSidebarNav"] li {{ margin: 2px 4px; }}
[data-testid="stSidebarNav"] li a {{
    position: relative;
    border-radius: 10px;
    padding: .45rem .6rem;
    transition: background .2s ease, transform .2s ease;
    overflow: hidden;
}}
[data-testid="stSidebarNav"] li a span {{ font-size: .88rem; }}
[data-testid="stSidebarNav"] li a::before {{
    content: ""; position: absolute; left: 0; top: 15%; bottom: 15%;
    width: 3px; border-radius: 2px;
    background: linear-gradient(180deg, #9BE800, #00A86B);
    transform: scaleY(0);
    transition: transform .22s ease;
}}
[data-testid="stSidebarNav"] li a:hover {{
    background: rgba(155, 232, 0, 0.07);
    transform: translateX(4px);
}}
[data-testid="stSidebarNav"] li a:hover::before {{ transform: scaleY(1); }}
[data-testid="stSidebarNav"] li a span {{ color: #C9CBE0; font-weight: 600; }}
[data-testid="stSidebarNav"] li a:hover span {{ color: #FAFAFA; }}
{_nav_css()}

/* ── Cards & metrics ──────────────────────────────────────────────────── */
[data-testid="stMetric"], [data-testid="metric-container"] {{
    background: #1A1A2E;
    border: 1px solid #2D2D4E;
    border-radius: 12px;
    padding: 14px;
    transition: transform .22s ease, border-color .22s ease, box-shadow .22s ease;
}}
[data-testid="stMetric"]:hover, [data-testid="metric-container"]:hover {{
    transform: translateY(-3px);
    border-color: #9BE800;
    box-shadow: 0 10px 28px rgba(0, 0, 0, .45);
}}
[data-testid="stMetric"] label {{ color: #8B8FA8 !important; }}
[data-testid="stMetricValue"] {{
    color: #FAFAFA !important;
    font-size: 1.55rem !important;   /* fits long team names without ellipsis */
}}

/* Page-link cards (home navigation grid) */
[data-testid="stPageLink"] a {{
    background: #1A1A2E;
    border: 1px solid #2D2D4E;
    border-radius: 12px;
    padding: .85rem 1rem !important;
    transition: transform .22s ease, border-color .22s ease, box-shadow .22s ease;
}}
[data-testid="stPageLink"] a:hover {{
    transform: translateY(-3px);
    border-color: #6D28D9;
    box-shadow: 0 12px 30px rgba(109, 40, 217, .25);
}}
[data-testid="stPageLink"] a p {{ color: #FAFAFA !important; font-weight: 600; }}

/* Tabs */
[data-testid="stTabs"] button {{ transition: color .2s ease; }}
[data-testid="stTabs"] button[aria-selected="true"] {{ color: #9BE800; }}

/* Dataframes */
.dataframe {{ background-color: #1A1A2E !important; color: #FAFAFA !important; }}

/* ── Keyframes ────────────────────────────────────────────────────────── */
@keyframes wcPageIn {{
    from {{ opacity: 0; transform: translateY(14px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
}}
@keyframes wcSlideGradient {{
    from {{ background-position: 0% 0; }}
    to   {{ background-position: 200% 0; }}
}}

/* ── Accessibility ────────────────────────────────────────────────────── */
@media (prefers-reduced-motion: reduce) {{
    *, *::before, *::after {{
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
    }}
}}
</style>
""", unsafe_allow_html=True)

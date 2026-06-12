"""
app/utils/intro.py
───────────────────
Retro-Bowl-style intro gate. A pixel footballer (a nod to Lamine Yamal —
dark hair, Spain red, #19) runs up and curls a ball into the net; the user
presses START to kick off and enter the dashboard.

Pure CSS keyframe animation (no JS/iframe) so it renders reliably inside
Streamlit. State is held in st.session_state so the gate only shows once per
session. Respects prefers-reduced-motion via the global theme.

Usage in app/main.py (right after inject_theme):
    from app.utils.intro import render_intro_gate
    if not render_intro_gate():
        st.stop()
"""
import streamlit as st

_STATE_KEY = "entered_tournament"


def _intro_css() -> str:
    return """
<style>
/* Hide chrome so the intro reads as a full-screen retro splash */
[data-testid="stSidebar"], [data-testid="stHeader"], [data-testid="stToolbar"] {
    display: none !important;
}
.block-container { padding-top: 1rem !important; max-width: 920px; }

@import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap');

.rb-stage {
    position: relative;
    border-radius: 16px;
    overflow: hidden;
    height: 430px;
    background:
        linear-gradient(180deg, #0a0a1c 0%, #0a0a1c 58%, #0c2a12 58%, #0c2a12 100%);
    border: 3px solid #9BE800;
    box-shadow: 0 0 0 4px #0a0a1c, 0 0 40px rgba(155,232,0,.25);
    image-rendering: pixelated;
}
/* Pitch stripes */
.rb-pitch {
    position: absolute; left: 0; right: 0; bottom: 0; height: 42%;
    background: repeating-linear-gradient(90deg,
        #0c2a12 0 38px, #0e3115 38px 76px);
}
/* CRT scanlines + vignette */
.rb-crt {
    position: absolute; inset: 0; z-index: 6; pointer-events: none;
    background:
        repeating-linear-gradient(0deg, rgba(0,0,0,.18) 0 2px, transparent 2px 4px),
        radial-gradient(120% 120% at 50% 30%, transparent 55%, rgba(0,0,0,.55) 100%);
    mix-blend-mode: multiply;
}
.rb-title {
    position: absolute; top: 18px; left: 0; right: 0; z-index: 5; text-align: center;
    font-family: 'Press Start 2P', monospace; color: #FFFFFF;
    font-size: 18px; letter-spacing: 1px;
    text-shadow: 3px 3px 0 #E0003C, 6px 6px 0 rgba(0,0,0,.4);
}
.rb-title small { color: #9BE800; font-size: 10px; display:block; margin-top: 8px; }

/* ── Goal (right) ─────────────────────────────────────────── */
.rb-goal { position: absolute; right: 7%; bottom: 30%; width: 120px; height: 130px; z-index: 2; }
.rb-goal .post { position: absolute; background: #f4f4f4; box-shadow: 2px 2px 0 rgba(0,0,0,.4); }
.rb-goal .left  { left: 0;  top: 0; width: 7px; height: 100%; }
.rb-goal .right { right: 0; top: 0; width: 7px; height: 100%; }
.rb-goal .bar   { left: 0; top: 0; width: 100%; height: 7px; }
.rb-goal .net {
    position: absolute; left: 7px; right: 7px; top: 7px; bottom: 0;
    background:
        repeating-linear-gradient(0deg, rgba(255,255,255,.22) 0 1px, transparent 1px 11px),
        repeating-linear-gradient(90deg, rgba(255,255,255,.22) 0 1px, transparent 1px 11px);
    transform-origin: left center;
    animation: rbNet 4.2s ease-in-out infinite;
}

/* ── Player (left) — stylised pixel footballer ────────────── */
.rb-player { position: absolute; left: 13%; bottom: 30%; width: 52px; height: 96px; z-index: 3;
    animation: rbRunup 4.2s ease-in-out infinite; }
.rb-player div { position: absolute; image-rendering: pixelated; }
.rb-hair  { top: 0; left: 12px; width: 26px; height: 16px; background: #1a1208; border-radius: 8px 8px 0 0; }
.rb-head  { top: 8px; left: 14px; width: 22px; height: 20px; background: #c98a5e; border-radius: 4px; }
.rb-body  { top: 26px; left: 8px; width: 34px; height: 34px; background: #E0003C;
    border-radius: 5px; box-shadow: inset 0 -8px 0 rgba(0,0,0,.18); }
.rb-num   { top: 32px; left: 16px; color: #fff; font-family: 'Press Start 2P'; font-size: 9px; }
.rb-arm   { top: 28px; left: 38px; width: 9px; height: 24px; background: #c98a5e; border-radius: 4px;
    transform: rotate(20deg); }
.rb-legf  { top: 58px; left: 22px; width: 11px; height: 30px; background: #11131f; border-radius: 3px;
    transform-origin: top center; animation: rbKick 4.2s ease-in-out infinite; }
.rb-legb  { top: 58px; left: 10px; width: 11px; height: 30px; background: #1d2030; border-radius: 3px;
    transform-origin: top center; animation: rbPlant 4.2s ease-in-out infinite; }
.rb-boot  { position: absolute; bottom: -4px; left: -2px; width: 16px; height: 7px; background: #9BE800; border-radius: 2px; }

/* ── Ball ─────────────────────────────────────────────────── */
.rb-ball {
    position: absolute; left: calc(13% + 40px); bottom: 30%;
    width: 20px; height: 20px; border-radius: 50%; z-index: 4;
    background: radial-gradient(circle at 35% 30%, #fff 60%, #cfd3dc 100%);
    box-shadow: inset -3px -3px 0 rgba(0,0,0,.18), 2px 2px 0 rgba(0,0,0,.35);
    animation: rbShoot 4.2s ease-in-out infinite;
}
.rb-ball::after {
    content: ""; position: absolute; inset: 5px; border-radius: 50%;
    background:
        radial-gradient(circle at 50% 50%, #11131f 0 3px, transparent 3px);
}

/* ── GOAL! flash ──────────────────────────────────────────── */
.rb-goalText {
    position: absolute; right: 9%; top: 30%; z-index: 5;
    font-family: 'Press Start 2P'; font-size: 26px; color: #9BE800;
    text-shadow: 3px 3px 0 #E0003C, 0 0 18px rgba(155,232,0,.7);
    opacity: 0; transform: scale(.4);
    animation: rbGoalText 4.2s ease-in-out infinite;
}
.rb-press {
    position: absolute; bottom: 14px; left: 0; right: 0; z-index: 5; text-align:center;
    font-family: 'Press Start 2P'; font-size: 11px; color: #fff;
    animation: rbBlink 1s steps(2) infinite;
}

@keyframes rbRunup {
    0%, 8% { transform: translateX(-26px); }
    18%, 100% { transform: translateX(0); }
}
@keyframes rbKick {
    0%, 14% { transform: rotate(28deg); }   /* wind up */
    22%     { transform: rotate(-46deg); }   /* strike */
    40%,100%{ transform: rotate(6deg); }
}
@keyframes rbPlant {
    0%,100% { transform: rotate(-6deg); }
    22% { transform: rotate(-10deg); }
}
@keyframes rbShoot {
    0%, 18%  { transform: translate(0, 0) scale(1) rotate(0deg); }
    /* arc: rightwards + up then down into the net */
    36%      { transform: translate(150px, -70px) scale(.9) rotate(360deg); }
    52%      { transform: translate(300px, -34px) scale(.8) rotate(680deg); }
    58%      { transform: translate(330px, -20px) scale(.8) rotate(760deg); } /* hit */
    59%, 100%{ transform: translate(330px, -20px) scale(.8) rotate(760deg); opacity: 1; }
}
@keyframes rbNet {
    0%, 57% { transform: scaleX(1) skewY(0deg); }
    61%     { transform: scaleX(1.10) skewY(-3deg); }
    66%     { transform: scaleX(.97) skewY(1deg); }
    72%,100%{ transform: scaleX(1) skewY(0deg); }
}
@keyframes rbGoalText {
    0%, 60%  { opacity: 0; transform: scale(.4) rotate(-6deg); }
    66%      { opacity: 1; transform: scale(1.15) rotate(-3deg); }
    80%      { opacity: 1; transform: scale(1) rotate(-3deg); }
    92%,100% { opacity: 0; transform: scale(1) rotate(-3deg); }
}
@keyframes rbBlink { 0%,49% { opacity: 1; } 50%,100% { opacity: .15; } }
</style>
"""


def _scene_html() -> str:
    return """
<div class="rb-stage">
  <div class="rb-pitch"></div>
  <div class="rb-title">FIFA WORLD CUP&nbsp;'26<small>★ PRESS START TO KICK OFF ★</small></div>

  <div class="rb-goal">
    <div class="post bar"></div>
    <div class="post left"></div>
    <div class="post right"></div>
    <div class="net"></div>
  </div>

  <div class="rb-player">
    <div class="rb-hair"></div>
    <div class="rb-head"></div>
    <div class="rb-body"></div>
    <div class="rb-num">19</div>
    <div class="rb-arm"></div>
    <div class="rb-legb"></div>
    <div class="rb-legf"><div class="rb-boot"></div></div>
  </div>

  <div class="rb-ball"></div>
  <div class="rb-goalText">GOAL!</div>
  <div class="rb-press">▶ PRESS START</div>
  <div class="rb-crt"></div>
</div>
"""


def render_intro_gate() -> bool:
    """
    Returns True once the user has entered. While on the splash, renders the
    retro scene + a START button and returns False (caller should st.stop()).
    """
    if st.session_state.get(_STATE_KEY):
        return True

    st.markdown(_intro_css(), unsafe_allow_html=True)
    st.markdown(_scene_html(), unsafe_allow_html=True)

    # The real gate: a centered START button styled like an arcade key.
    _, mid, _ = st.columns([1, 1.1, 1])
    with mid:
        st.markdown("""
        <style>
        div[data-testid="stButton"] > button {
            width: 100%;
            background: #9BE800; color: #0a0a1c;
            font-family: 'Press Start 2P', monospace; font-size: 13px;
            border: 0; border-radius: 10px; padding: .9rem 0;
            box-shadow: 0 6px 0 #5e8c00; transition: transform .08s ease, box-shadow .08s ease;
        }
        div[data-testid="stButton"] > button:hover { transform: translateY(-2px); box-shadow: 0 8px 0 #5e8c00; }
        div[data-testid="stButton"] > button:active { transform: translateY(4px); box-shadow: 0 2px 0 #5e8c00; }
        </style>
        """, unsafe_allow_html=True)
        if st.button("⚽  SHOOT TO ENTER", key="enter_btn"):
            st.session_state[_STATE_KEY] = True
            st.rerun()

    st.caption("World Cup 2026 Analytics · press start to enter the dashboard")
    return False

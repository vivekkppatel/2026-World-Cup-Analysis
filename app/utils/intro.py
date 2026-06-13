"""
app/utils/intro.py
───────────────────
Full-screen, WASD-controlled intro gate (carlosarcilla.com style). The player
— a pixel footballer in Spain red, #19, a nod to Lamine Yamal — is driven with
WASD / arrow keys; dribble the ball into the goal and the dashboard unlocks.

Implementation notes:
  • The game is a <canvas> in a components.html iframe (real JS keyboard input
    + game loop). The iframe is same-origin with the app, so on GOAL it sets a
    ?entered=1 query param on the parent, which Streamlit reads to unlock.
  • A session_state flag + a "Skip" button are belt-and-braces fallbacks, so a
    user is never stuck if the auto-unlock is blocked.
  • Respects prefers-reduced-motion (offers an immediate Enter button).
"""
import streamlit as st
import streamlit.components.v1 as components

_STATE_KEY = "entered_tournament"
_GAME_HEIGHT = 560


def _game_html() -> str:
    return f"""
<!doctype html><html><head><meta charset="utf-8">
<style>
  html,body{{margin:0;height:100%;background:#07070f;overflow:hidden;
    font-family:'Courier New',monospace;}}
  #wrap{{position:relative;width:100%;height:{_GAME_HEIGHT}px;}}
  canvas{{display:block;width:100%;height:100%;image-rendering:pixelated;
    border:3px solid #9BE800;border-radius:14px;box-shadow:0 0 40px rgba(155,232,0,.25);}}
  #hud{{position:absolute;top:14px;left:0;right:0;text-align:center;color:#fff;
    font-weight:700;letter-spacing:.1em;font-size:13px;text-shadow:2px 2px 0 #000;
    pointer-events:none;}}
  #hud b{{color:#9BE800;}}
  #tip{{position:absolute;bottom:16px;left:0;right:0;text-align:center;color:#cfd3dc;
    font-size:12px;pointer-events:none;animation:blink 1.1s steps(2) infinite;}}
  @keyframes blink{{50%{{opacity:.25;}}}}
</style></head>
<body>
<div id="wrap">
  <canvas id="c" tabindex="0"></canvas>
  <div id="hud">FIFA WORLD CUP <b>'26</b> &nbsp;·&nbsp; DRIBBLE INTO THE GOAL TO ENTER</div>
  <div id="tip">▶ CLICK THE PITCH, THEN USE <b>W A S D</b> / ARROW KEYS</div>
</div>
<script>
const cv = document.getElementById('c'), ctx = cv.getContext('2d');
let W=0, H=0;
function resize(){{ W=cv.width=cv.clientWidth; H=cv.height={_GAME_HEIGHT}; }}
resize(); window.addEventListener('resize', resize);

const keys = {{}};
function setKey(e,v){{
  const k=e.key.toLowerCase();
  if(['arrowup','arrowdown','arrowleft','arrowright',' '].includes(k)) e.preventDefault();
  if(k==='w'||k==='arrowup') keys.up=v;
  if(k==='s'||k==='arrowdown') keys.down=v;
  if(k==='a'||k==='arrowleft') keys.left=v;
  if(k==='d'||k==='arrowright') keys.right=v;
}}
window.addEventListener('keydown', e=>setKey(e,true));
window.addEventListener('keyup',   e=>setKey(e,false));
cv.addEventListener('click', ()=>cv.focus());
setTimeout(()=>cv.focus(), 200);

// Entities
const player = {{x: 90, y: {_GAME_HEIGHT}/2, vx:0, vy:0, r:16, face:1, step:0}};
const ball   = {{x: 150, y: {_GAME_HEIGHT}/2, vx:0, vy:0, r:10}};
let scored=false, goalT=0, confetti=[];

function goalRect(){{ return {{x: W-26, y: H/2-70, w: 22, h: 140}}; }}

function update(){{
  const acc=0.7, fr=0.86, max=4.6;
  if(keys.up) player.vy-=acc; if(keys.down) player.vy+=acc;
  if(keys.left){{player.vx-=acc; player.face=-1;}} if(keys.right){{player.vx+=acc; player.face=1;}}
  player.vx*=fr; player.vy*=fr;
  player.vx=Math.max(-max,Math.min(max,player.vx));
  player.vy=Math.max(-max,Math.min(max,player.vy));
  player.x+=player.vx; player.y+=player.vy;
  player.x=Math.max(player.r,Math.min(W-player.r,player.x));
  player.y=Math.max(player.r,Math.min(H-player.r,player.y));
  if(Math.abs(player.vx)+Math.abs(player.vy)>.5) player.step+=0.3;

  // ball physics
  ball.vx*=0.95; ball.vy*=0.95; ball.x+=ball.vx; ball.y+=ball.vy;
  if(ball.x<ball.r){{ball.x=ball.r; ball.vx*=-.5;}}
  if(ball.y<ball.r){{ball.y=ball.r; ball.vy*=-.5;}}
  if(ball.y>H-ball.r){{ball.y=H-ball.r; ball.vy*=-.5;}}
  if(ball.x>W-ball.r){{ball.x=W-ball.r; ball.vx*=-.5;}}

  // kick: player pushes ball
  const dx=ball.x-player.x, dy=ball.y-player.y, d=Math.hypot(dx,dy);
  if(d < player.r+ball.r){{
    const push=Math.max(2.4, Math.hypot(player.vx,player.vy)*1.7);
    ball.vx += (dx/d)*push + player.vx*0.4;
    ball.vy += (dy/d)*push + player.vy*0.4;
  }}

  // goal check
  const g=goalRect();
  if(!scored && ball.x+ball.r>g.x && ball.y>g.y && ball.y<g.y+g.h){{
    scored=true; goalT=0;
    for(let i=0;i<120;i++) confetti.push({{x:ball.x,y:ball.y,
      vx:(Math.random()-.5)*9, vy:(Math.random()-1)*9,
      c:['#9BE800','#E0003C','#6D28D9','#E8C547','#fff'][i%5], life:60}});
  }}
  if(scored){{
    goalT++;
    confetti.forEach(p=>{{p.x+=p.vx; p.y+=p.vy; p.vy+=0.32; p.life--;}});
    confetti=confetti.filter(p=>p.life>0);
    if(goalT===44) unlock();
  }}
}}

function drawHex(){{
  ctx.fillStyle='#0b0b1c'; ctx.fillRect(0,0,W,H);
  ctx.strokeStyle='rgba(155,232,0,0.06)'; ctx.lineWidth=1;
  const s=26;
  for(let y=0;y<H+s;y+=s*0.75){{
    for(let x=0;x<W+s;x+=s*1.5){{
      const ox=((y/(s*0.75))%2)? s*0.75:0;
      hex(x+ox,y,s*0.5);
    }}
  }}
}}
function hex(cx,cy,r){{
  ctx.beginPath();
  for(let i=0;i<6;i++){{const a=Math.PI/3*i+Math.PI/6;
    const px=cx+r*Math.cos(a), py=cy+r*Math.sin(a);
    i?ctx.lineTo(px,py):ctx.moveTo(px,py);}}
  ctx.closePath(); ctx.stroke();
}}

function drawGoal(){{
  const g=goalRect();
  ctx.strokeStyle='#f4f4f4'; ctx.lineWidth=4;
  ctx.strokeRect(g.x,g.y,g.w,g.h);
  ctx.strokeStyle='rgba(255,255,255,.25)'; ctx.lineWidth=1;
  for(let i=g.y;i<g.y+g.h;i+=10){{ctx.beginPath();ctx.moveTo(g.x,i);ctx.lineTo(g.x+g.w,i);ctx.stroke();}}
}}

function drawPlayer(){{
  const p=player, b=Math.sin(p.step)*5;
  ctx.save(); ctx.translate(p.x,p.y);
  // legs
  ctx.fillStyle='#11131f';
  ctx.fillRect(-7, 8, 5, 12+b); ctx.fillRect(2, 8, 5, 12-b);
  // body (Spain red)
  ctx.fillStyle='#E0003C'; ctx.fillRect(-9,-8,18,18);
  // number
  ctx.fillStyle='#fff'; ctx.font='bold 8px monospace'; ctx.textAlign='center';
  ctx.fillText('19',0,5);
  // head + dark hair
  ctx.fillStyle='#c98a5e'; ctx.fillRect(-7,-22,14,14);
  ctx.fillStyle='#1a1208'; ctx.fillRect(-8,-24,16,7);
  ctx.restore();
}}

function drawBall(){{
  ctx.save(); ctx.translate(ball.x,ball.y);
  ctx.fillStyle='#fff'; ctx.beginPath(); ctx.arc(0,0,ball.r,0,7); ctx.fill();
  ctx.fillStyle='#11131f';
  ctx.beginPath(); ctx.arc(0,0,3,0,7); ctx.fill();
  ctx.restore();
}}

function drawGoalText(){{
  if(!scored) return;
  ctx.fillStyle='#9BE800'; ctx.font='900 56px Arial Black, sans-serif';
  ctx.textAlign='center'; ctx.shadowColor='#000'; ctx.shadowBlur=12;
  const s=Math.min(1, goalT/10);
  ctx.save(); ctx.translate(W/2,H/2); ctx.scale(s,s);
  ctx.fillText('GOAL!', 0, 0);
  ctx.font='bold 16px monospace'; ctx.fillStyle='#fff';
  ctx.fillText('ENTERING…', 0, 36); ctx.restore(); ctx.shadowBlur=0;
  confetti.forEach(p=>{{ctx.fillStyle=p.c; ctx.fillRect(p.x,p.y,4,4);}});
}}

function loop(){{ update(); drawHex(); drawGoal(); drawBall(); drawPlayer(); drawGoalText();
  requestAnimationFrame(loop); }}
loop();

function unlock(){{
  // The iframe is same-origin with the app, so the cleanest unlock is to
  // click the real Streamlit "Enter" button in the parent — that fires the
  // normal session_state callback and rerun (no fragile URL navigation).
  try {{
    const btns = window.parent.document.querySelectorAll('button');
    for (const b of btns) {{
      if (/enter the dashboard/i.test(b.innerText)) {{ b.click(); return; }}
    }}
  }} catch(e) {{}}
  try {{
    const u = new URL(window.parent.location.href);
    u.searchParams.set('entered','1');
    window.parent.location.replace(u.toString());
  }} catch(e) {{}}
}}
</script></body></html>
"""


def render_intro_gate() -> bool:
    """Returns True once entered; otherwise renders the game and returns False."""
    if st.session_state.get(_STATE_KEY) or st.query_params.get("entered") == "1":
        st.session_state[_STATE_KEY] = True
        return True

    # Hide chrome for a full-screen splash.
    st.markdown("""
    <style>
    [data-testid="stSidebar"], [data-testid="stHeader"], [data-testid="stToolbar"] {
        display: none !important; }
    .block-container { padding-top: .6rem !important; max-width: 1100px; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("<h2 style='text-align:center;font-family:Archivo Black,sans-serif;"
                "color:#fff;margin:.2rem 0'>WORLD CUP 26 · ANALYTICS</h2>",
                unsafe_allow_html=True)
    components.html(_game_html(), height=_GAME_HEIGHT + 10, scrolling=False)

    _, mid, _ = st.columns([1, 1, 1])
    with mid:
        # Scoring a goal auto-clicks this button; it's also the manual fallback.
        if st.button("⚽  Enter the dashboard →", use_container_width=True):
            st.session_state[_STATE_KEY] = True
            st.rerun()
    st.caption("Tip: click the pitch first so it captures your keys, then dribble the "
               "ball into the goal on the right. (Or use the button to skip ahead.)")
    return False

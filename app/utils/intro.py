"""
app/utils/intro.py
───────────────────
Full-screen, roam-anywhere WASD intro (carlosarcilla.com style). The player —
a pixel footballer in Spain red, #19, a nod to Lamine Yamal — is driven with
WASD / arrow keys around a fully animated soccer pitch (markings, floodlights,
drifting balls, grass shimmer). Dribble the ball into the goal and the
dashboard unlocks.

Unlock: the game runs in a same-origin components.html iframe, so on GOAL it
clicks the real Streamlit "Enter" button in the parent (reliable session_state
rerun — full-page URL nav is unreliable because Streamlit strips query params).
A manual Enter button and a session_state flag are belt-and-braces fallbacks.
"""
import streamlit as st
import streamlit.components.v1 as components

_STATE_KEY = "entered_tournament"
_GAME_HEIGHT = 680

# Plain template (no f-string) so the JS braces need no escaping; __H__ is the
# canvas height, substituted below.
_GAME_TEMPLATE = r"""
<!doctype html><html><head><meta charset="utf-8">
<style>
  html,body{margin:0;height:100%;background:#07070f;overflow:hidden;
    font-family:'Courier New',monospace;}
  #wrap{position:relative;width:100%;height:__H__px;}
  canvas{display:block;width:100%;height:100%;
    border:3px solid #9BE800;border-radius:16px;
    box-shadow:0 0 60px rgba(155,232,0,.28), inset 0 0 80px rgba(0,0,0,.5);cursor:none;}
  .ui{position:absolute;left:0;right:0;text-align:center;color:#fff;pointer-events:none;
    text-shadow:2px 2px 0 #000;}
  #hud{top:16px;font-weight:800;letter-spacing:.14em;font-size:14px;}
  #hud b{color:#9BE800;}
  #tip{bottom:18px;font-size:12px;color:#dfe2f0;animation:blink 1.1s steps(2) infinite;}
  @keyframes blink{50%{opacity:.25;}}
  #focusmsg{top:50%;transform:translateY(-50%);font-size:18px;font-weight:800;
    color:#9BE800;transition:opacity .3s;}
</style></head>
<body>
<div id="wrap">
  <canvas id="c" tabindex="0"></canvas>
  <div class="ui" id="hud">FIFA WORLD CUP <b>'26</b> &nbsp;·&nbsp; DRIBBLE THE BALL INTO THE GOAL &nbsp;→</div>
  <div class="ui" id="tip">CLICK THE PITCH · MOVE WITH <b>W A S D</b> / ARROW KEYS · ROAM ANYWHERE</div>
  <div class="ui" id="focusmsg">▶ CLICK TO PLAY</div>
</div>
<script>
const cv=document.getElementById('c'), ctx=cv.getContext('2d');
const focusmsg=document.getElementById('focusmsg');
let W=0,H=0,focused=false,t=0,placed=false;
function measureW(){
  return Math.max(
    document.documentElement.clientWidth||0,
    document.body.clientWidth||0,
    cv.clientWidth||0, window.innerWidth||0, 0);
}
function resize(){
  const w=measureW();
  if(w>40){ W=cv.width=w; }            // ignore bogus tiny pre-layout widths
  H=cv.height=__H__;
  if(!placed && W>240){                // place entities once we have a real width
    player.x=W*0.14; player.y=H/2; player.vx=player.vy=0;
    ball.x=W*0.22; ball.y=H/2; ball.vx=ball.vy=0;
    placed=true;
  }
}
addEventListener('resize',resize);
addEventListener('load',resize);
// Components iframes don't reliably fire resize on first layout — observe + poll.
try{ new ResizeObserver(resize).observe(document.documentElement); }catch(e){}
let _tries=0; const _iv=setInterval(()=>{ resize(); if(++_tries>30||placed) clearInterval(_iv); },80);

const keys={};
function setKey(e,v){
  const k=e.key.toLowerCase();
  if(['arrowup','arrowdown','arrowleft','arrowright',' '].includes(k)) e.preventDefault();
  if(k==='w'||k==='arrowup')keys.up=v;
  if(k==='s'||k==='arrowdown')keys.down=v;
  if(k==='a'||k==='arrowleft')keys.left=v;
  if(k==='d'||k==='arrowright')keys.right=v;
}
addEventListener('keydown',e=>setKey(e,true));
addEventListener('keyup',e=>setKey(e,false));
function focusGame(){ cv.focus(); focused=true; focusmsg.style.opacity=0; }
cv.addEventListener('click',focusGame);
cv.addEventListener('mousedown',focusGame);

const player={x:120,y:__H__/2,vx:0,vy:0,r:17,face:1,step:0};
const ball={x:185,y:__H__/2,vx:0,vy:0,r:11,spin:0};
let scored=false,goalT=0,confetti=[],ripple=0;
// ambient drifting background balls (parallax)
const bg=[];
for(let i=0;i<7;i++) bg.push({x:Math.random()*1000,y:Math.random()*__H__,
  r:6+Math.random()*10, vx:-.3-Math.random()*.5, a:.05+Math.random()*.06});
resize();  // now that player/ball exist, size and place them

function goalRect(){ return {x:W-30,y:H/2-78,w:24,h:156}; }

function update(){
  t++;
  const acc=.8,fr=.85,max=5.2;
  if(keys.up)player.vy-=acc; if(keys.down)player.vy+=acc;
  if(keys.left){player.vx-=acc;player.face=-1;} if(keys.right){player.vx+=acc;player.face=1;}
  player.vx*=fr; player.vy*=fr;
  player.vx=Math.max(-max,Math.min(max,player.vx));
  player.vy=Math.max(-max,Math.min(max,player.vy));
  player.x+=player.vx; player.y+=player.vy;
  player.x=Math.max(player.r,Math.min(W-player.r,player.x));
  player.y=Math.max(player.r,Math.min(H-player.r,player.y));
  if(Math.abs(player.vx)+Math.abs(player.vy)>.6) player.step+=0.32;

  ball.vx*=.955; ball.vy*=.955; ball.x+=ball.vx; ball.y+=ball.vy;
  ball.spin+=ball.vx*0.05;
  if(ball.x<ball.r){ball.x=ball.r;ball.vx*=-.55;}
  if(ball.y<ball.r){ball.y=ball.r;ball.vy*=-.55;}
  if(ball.y>H-ball.r){ball.y=H-ball.r;ball.vy*=-.55;}
  if(ball.x>W-ball.r){ball.x=W-ball.r;ball.vx*=-.55;}

  const dx=ball.x-player.x,dy=ball.y-player.y,d=Math.hypot(dx,dy)||1;
  if(d<player.r+ball.r){
    const push=Math.max(2.8,Math.hypot(player.vx,player.vy)*1.8);
    ball.vx+=(dx/d)*push+player.vx*.4; ball.vy+=(dy/d)*push+player.vy*.4;
  }

  const g=goalRect();
  if(!scored && ball.x+ball.r>g.x && ball.y>g.y && ball.y<g.y+g.h){
    scored=true; goalT=0; ripple=1;
    for(let i=0;i<160;i++) confetti.push({x:ball.x,y:ball.y,
      vx:(Math.random()-.5)*11,vy:(Math.random()-1)*11,
      c:['#9BE800','#E0003C','#6D28D9','#E8C547','#fff'][i%5],life:70});
  }
  if(scored){ goalT++; ripple*=.93;
    confetti.forEach(p=>{p.x+=p.vx;p.y+=p.vy;p.vy+=.34;p.life--;});
    confetti=confetti.filter(p=>p.life>0);
    if(goalT===46) unlock();
  }
  bg.forEach(b=>{b.x+=b.vx; if(b.x<-20)b.x=W+20;});
}

function drawPitch(){
  // grass stripes
  const stripe=Math.max(50,W/14);
  for(let i=0,x=0;x<W;i++,x+=stripe){
    ctx.fillStyle=(i%2)?'#0c2a12':'#0e3417';
    ctx.fillRect(x,0,stripe,H);
  }
  // subtle vignette
  const vg=ctx.createRadialGradient(W/2,H/2,H*0.2,W/2,H/2,W*0.75);
  vg.addColorStop(0,'rgba(0,0,0,0)'); vg.addColorStop(1,'rgba(0,0,0,.55)');
  ctx.fillStyle=vg; ctx.fillRect(0,0,W,H);
  // markings
  ctx.strokeStyle='rgba(255,255,255,.30)'; ctx.lineWidth=2;
  ctx.strokeRect(14,14,W-28,H-28);                       // boundary
  ctx.beginPath(); ctx.moveTo(W/2,14); ctx.lineTo(W/2,H-14); ctx.stroke(); // halfway
  ctx.beginPath(); ctx.arc(W/2,H/2,64,0,7); ctx.stroke();  // centre circle
  ctx.beginPath(); ctx.arc(W/2,H/2,3,0,7); ctx.fillStyle='rgba(255,255,255,.4)'; ctx.fill();
  // right penalty + goal area
  ctx.strokeRect(W-14-120,H/2-95,120,190);
  ctx.strokeRect(W-14-46,H/2-50,46,100);
  // left mirror (decorative)
  ctx.strokeRect(14,H/2-95,120,190);
  ctx.strokeRect(14,H/2-50,46,100);
  // floodlights
  for(const c of [[60,50],[W-60,50],[60,H-50],[W-60,H-50]]){
    const p=0.5+0.5*Math.sin(t*0.03+c[0]);
    const lg=ctx.createRadialGradient(c[0],c[1],0,c[0],c[1],200);
    lg.addColorStop(0,'rgba(200,255,180,'+(0.05+0.04*p)+')');
    lg.addColorStop(1,'rgba(0,0,0,0)');
    ctx.fillStyle=lg; ctx.fillRect(0,0,W,H);
  }
  // ambient drifting balls
  bg.forEach(b=>{ ctx.fillStyle='rgba(255,255,255,'+b.a+')';
    ctx.beginPath(); ctx.arc(b.x,b.y,b.r,0,7); ctx.fill(); });
}

function drawGoal(){
  const g=goalRect();
  ctx.save();
  if(scored){ ctx.translate(g.x+Math.sin(goalT*0.6)*ripple*5,0); }
  ctx.strokeStyle='#f6f6f6'; ctx.lineWidth=5; ctx.strokeRect(g.x,g.y,g.w,g.h);
  ctx.strokeStyle='rgba(255,255,255,.28)'; ctx.lineWidth=1;
  for(let i=g.y;i<g.y+g.h;i+=9){ctx.beginPath();ctx.moveTo(g.x,i);ctx.lineTo(g.x+g.w,i);ctx.stroke();}
  for(let j=g.x;j<g.x+g.w;j+=8){ctx.beginPath();ctx.moveTo(j,g.y);ctx.lineTo(j,g.y+g.h);ctx.stroke();}
  ctx.restore();
}

function shadow(x,y,r){ ctx.fillStyle='rgba(0,0,0,.30)';
  ctx.beginPath(); ctx.ellipse(x,y+r-2,r*0.9,r*0.4,0,0,7); ctx.fill(); }

function drawPlayer(){
  const p=player,b=Math.sin(p.step)*6;
  shadow(p.x,p.y+10,p.r);
  ctx.save(); ctx.translate(p.x,p.y);
  ctx.fillStyle='#11131f'; ctx.fillRect(-8,8,6,13+b); ctx.fillRect(2,8,6,13-b);
  ctx.fillStyle='#9BE800'; ctx.fillRect(-8,20+b,6,4); ctx.fillRect(2,20-b,6,4); // boots
  ctx.fillStyle='#E0003C'; ctx.fillRect(-10,-9,20,20);                          // jersey
  ctx.fillStyle='#fff'; ctx.font='bold 9px monospace'; ctx.textAlign='center'; ctx.fillText('19',0,6);
  ctx.fillStyle='#c98a5e'; ctx.fillRect(-8,-24,16,15);                          // head
  ctx.fillStyle='#1a1208'; ctx.fillRect(-9,-26,18,8);                           // hair
  ctx.restore();
}

function drawBall(){
  shadow(ball.x,ball.y+6,ball.r);
  ctx.save(); ctx.translate(ball.x,ball.y); ctx.rotate(ball.spin);
  ctx.fillStyle='#fff'; ctx.beginPath(); ctx.arc(0,0,ball.r,0,7); ctx.fill();
  ctx.fillStyle='#11131f';
  ctx.beginPath(); ctx.arc(0,0,3.4,0,7); ctx.fill();
  for(let i=0;i<5;i++){const a=i/5*7; ctx.beginPath();
    ctx.arc(Math.cos(a)*7,Math.sin(a)*7,1.6,0,7); ctx.fill();}
  ctx.restore();
}

function drawGoalText(){
  if(!scored) return;
  const s=Math.min(1,goalT/9);
  ctx.save(); ctx.translate(W/2,H/2); ctx.scale(s,s);
  ctx.shadowColor='#000'; ctx.shadowBlur=16;
  ctx.fillStyle='#9BE800'; ctx.font='900 72px Arial Black, sans-serif'; ctx.textAlign='center';
  ctx.fillText('GOAL!',0,0);
  ctx.shadowBlur=0; ctx.fillStyle='#fff'; ctx.font='bold 18px monospace';
  ctx.fillText('ENTERING THE DASHBOARD…',0,42); ctx.restore();
  confetti.forEach(p=>{ctx.fillStyle=p.c; ctx.fillRect(p.x,p.y,4,4);});
}

function step(){ update(); drawPitch(); drawGoal(); drawBall(); drawPlayer(); drawGoalText(); }
// setInterval (not requestAnimationFrame) so motion survives embedded/iframe
// visibility quirks where rAF can pause.
setInterval(step, 1000/60);
step();

function unlock(){
  try{
    const btns=window.parent.document.querySelectorAll('button');
    for(const b of btns){ if(/enter the dashboard/i.test(b.innerText)){ b.click(); return; } }
  }catch(e){}
  try{ const u=new URL(window.parent.location.href); u.searchParams.set('entered','1');
    window.parent.location.replace(u.toString()); }catch(e){}
}
</script></body></html>
"""


def _game_html() -> str:
    return _GAME_TEMPLATE.replace("__H__", str(_GAME_HEIGHT))


def render_intro_gate() -> bool:
    """Returns True once entered; otherwise renders the game and returns False."""
    if st.session_state.get(_STATE_KEY) or st.query_params.get("entered") == "1":
        st.session_state[_STATE_KEY] = True
        return True

    # Full-screen splash: hide all Streamlit chrome and padding.
    st.markdown("""
    <style>
    [data-testid="stSidebar"], [data-testid="stHeader"], [data-testid="stToolbar"] {
        display:none !important; }
    [data-testid="stAppViewContainer"] .block-container {
        padding:.4rem 1rem 0 1rem !important; max-width:100% !important; }
    [data-testid="stMainBlockContainer"] { padding-top:.4rem !important; }
    </style>
    """, unsafe_allow_html=True)

    components.html(_game_html(), height=_GAME_HEIGHT + 8, scrolling=False)

    _, mid, _ = st.columns([2, 1, 2])
    with mid:
        if st.button("⚽  Enter the dashboard →", use_container_width=True):
            st.session_state[_STATE_KEY] = True
            st.rerun()
    return False

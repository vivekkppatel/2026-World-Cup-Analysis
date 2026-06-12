"""
app/utils/bracket_view.py
──────────────────────────
Mirrored 32-team knockout bracket as an SVG (green-on-black, FIFA-26 retro),
in two flavours:

    kind="expected"  → the model's modal bracket (predicted_bracket table)
    kind="actual"    → reality as it resolves (matches table)

The bracket topology is read from the matches table's placeholder encoding
(home/away_placeholder: group codes like '2A' for Round-of-32 slots, 'W74'
for "winner of match 74" in later rounds), so the tree is data-driven, not
hardcoded. Wrap the render in an st.fragment(run_every=...) for self-update.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import pandas as pd

from database.db import engine

_W = re.compile(r"^W(\d+)$")
LIME, DIM, BLACK, GOLD, RED = "#9BE800", "#3a5d12", "#0b0b1c", "#E8C547", "#E0003C"

# Canvas geometry
CW, CH = 1040, 460          # viewBox
COL_X_LEFT = [70, 196, 322, 440]      # R32, R16, QF, SF  (x-centres, left half)
COL_X_RIGHT = [CW - x for x in COL_X_LEFT]
FINAL_X = CW / 2
BOX_W, BOX_H = 104, 34
TOP, BOT = 56, CH - 18      # vertical band for the 8 R32 rows


@dataclass
class Node:
    num: int
    stage: str
    home: str           # resolved/predicted label for the top slot
    away: str           # bottom slot
    winner_side: str    # 'home' | 'away' | '' (unknown)
    src: list[int] = field(default_factory=list)   # child match numbers (W##)
    x: float = 0.0
    y: float = 0.0


def _tla_map() -> dict[str, str]:
    df = pd.read_sql("SELECT name, tla FROM teams WHERE tla IS NOT NULL", engine)
    return {r["name"]: r["tla"] for _, r in df.iterrows()}


def _short(label: str | None, tla: dict[str, str]) -> str:
    """Compact a team name or placeholder code into a bracket-sized label."""
    if not label:
        return "—"
    if label in tla:
        return tla[label]
    s = str(label)
    if "/" in s:                       # best-third pool, e.g. '3A/B/C/D/F'
        return "3rd"
    if _W.match(s):                    # 'W74' → 'W74' is fine but shorten
        return "W" + s[1:]
    return s[:3].upper() if len(s) <= 4 else s[:9]


def _load_nodes(kind: str) -> dict[int, Node]:
    """Build the match-number → Node map for the chosen bracket flavour."""
    ko = pd.read_sql("""
        SELECT m.fifa_match_num AS num, m.stage,
               m.home_placeholder, m.away_placeholder, m.winner,
               th.name AS home_team, ta.name AS away_team
        FROM matches m
        LEFT JOIN teams th ON th.id = m.home_team_id
        LEFT JOIN teams ta ON ta.id = m.away_team_id
        WHERE m.stage IN ('LAST_32','LAST_16','QUARTER_FINALS','SEMI_FINALS','FINAL')
          AND m.fifa_match_num IS NOT NULL
        ORDER BY m.fifa_match_num
    """, engine)

    pred = {}
    if kind == "expected":
        pb = pd.read_sql(
            "SELECT fifa_match_num, home_team, away_team, winner FROM predicted_bracket",
            engine)
        pred = {int(r["fifa_match_num"]): r for _, r in pb.iterrows()}

    nodes: dict[int, Node] = {}
    for _, r in ko.iterrows():
        num = int(r["num"])
        if kind == "expected" and num in pred:
            p = pred[num]
            home, away = p["home_team"], p["away_team"]
            winner_side = ("home" if p["winner"] == home
                           else "away" if p["winner"] == away else "")
        else:  # actual
            home = r["home_team"] or r["home_placeholder"]
            away = r["away_team"] or r["away_placeholder"]
            winner_side = ("home" if r["winner"] == "HOME"
                           else "away" if r["winner"] == "AWAY" else "")
        src = []
        for ph in (r["home_placeholder"], r["away_placeholder"]):
            m = _W.match(str(ph or ""))
            if m:
                src.append(int(m.group(1)))
        nodes[num] = Node(num, r["stage"], home, away, winner_side, src)
    return nodes


def _leaves(num: int, nodes: dict[int, Node]) -> list[int]:
    """R32 match numbers under `num`, in top-to-bottom display order."""
    n = nodes[num]
    if not n.src:
        return [num]
    return _leaves(n.src[0], nodes) + _leaves(n.src[1], nodes)


def _assign_y(num: int, nodes: dict[int, Node], leaf_y: dict[int, float]) -> float:
    n = nodes[num]
    if not n.src:
        n.y = leaf_y[num]
    else:
        n.y = sum(_assign_y(s, nodes, leaf_y) for s in n.src) / len(n.src)
    return n.y


def _col_x(stage: str, half: str) -> float:
    idx = {"LAST_32": 0, "LAST_16": 1, "QUARTER_FINALS": 2, "SEMI_FINALS": 3}[stage]
    return COL_X_LEFT[idx] if half == "left" else COL_X_RIGHT[idx]


def _box_svg(n: Node, tla: dict[str, str]) -> str:
    x, y = n.x - BOX_W / 2, n.y - BOX_H / 2
    win_home = n.winner_side == "home"
    win_away = n.winner_side == "away"

    def slot(ty: float, label: str, won: bool) -> str:
        bg = LIME if won else "#11131f"
        fg = BLACK if won else "#cfd3dc"
        return (f'<rect x="{x}" y="{ty}" width="{BOX_W}" height="{BOX_H/2}" rx="3" '
                f'fill="{bg}" stroke="{DIM}" stroke-width="1"/>'
                f'<text x="{x+7}" y="{ty+BOX_H/2-4}" fill="{fg}" '
                f'font-size="9" font-family="monospace" font-weight="bold">'
                f'{_short(label, tla)}</text>')

    return slot(y, n.home, win_home) + slot(y + BOX_H / 2, n.away, win_away)


def _connector(child: Node, parent: Node) -> str:
    """Elbow line from a child box to its parent box."""
    going_right = parent.x > child.x
    cx = child.x + (BOX_W / 2 if going_right else -BOX_W / 2)
    px = parent.x - (BOX_W / 2 if going_right else -BOX_W / 2)
    midx = (cx + px) / 2
    return (f'<polyline points="{cx},{child.y} {midx},{child.y} '
            f'{midx},{parent.y} {px},{parent.y}" '
            f'fill="none" stroke="{DIM}" stroke-width="2"/>')


def render_bracket_svg(kind: str) -> str:
    """Return the full bracket SVG string for kind in {'expected','actual'}."""
    nodes = _load_nodes(kind)
    if 104 not in nodes:
        return '<p style="color:#8B8FA8">Run the bracket simulation / refresh first.</p>'
    tla = _tla_map()
    final = nodes[104]
    sf_left, sf_right = (final.src + [None, None])[:2]

    # Leaf (R32) vertical slots — 8 per half.
    left_leaves = _leaves(sf_left, nodes) if sf_left else []
    right_leaves = _leaves(sf_right, nodes) if sf_right else []
    rows = max(len(left_leaves), len(right_leaves), 1)
    step = (BOT - TOP) / max(rows, 1)
    leaf_y = {}
    for i, lf in enumerate(left_leaves):
        leaf_y[lf] = TOP + i * step + step / 2
    for i, lf in enumerate(right_leaves):
        leaf_y[lf] = TOP + i * step + step / 2

    # Assign x/y to every node.
    for half, root in (("left", sf_left), ("right", sf_right)):
        if root is None:
            continue
        _assign_y(root, nodes, leaf_y)
        for num, n in nodes.items():
            if n.stage != "FINAL" and num in _descendants(root, nodes):
                n.x = _col_x(n.stage, half)
    final.x, final.y = FINAL_X, (nodes[sf_left].y + nodes[sf_right].y) / 2 if sf_left and sf_right else CH / 2

    # Draw: connectors first (under), then boxes, then title.
    parts = [f'<svg viewBox="0 0 {CW} {CH}" xmlns="http://www.w3.org/2000/svg" '
             f'style="width:100%;height:auto;background:{BLACK};'
             f'border:2px solid {LIME};border-radius:14px">']
    for num, n in nodes.items():
        for s in n.src:
            if s in nodes:
                parts.append(_connector(nodes[s], n))
    # connectors SF→Final
    for s in final.src:
        if s in nodes:
            parts.append(_connector(nodes[s], final))
    for n in nodes.values():
        parts.append(_box_svg(n, tla))

    # Centre title
    parts.append(
        f'<text x="{FINAL_X}" y="30" text-anchor="middle" fill="#fff" '
        f'font-size="22" font-weight="900" font-family="Arial Black, sans-serif">FIFA</text>'
        f'<text x="{FINAL_X}" y="46" text-anchor="middle" fill="{LIME}" '
        f'font-size="12" font-style="italic" font-family="Georgia, serif">'
        f"World Cup '26</text>")
    parts.append("</svg>")
    return "".join(parts)


def _descendants(num: int, nodes: dict[int, Node]) -> set[int]:
    out = {num}
    for s in nodes[num].src:
        if s in nodes:
            out |= _descendants(s, nodes)
    return out

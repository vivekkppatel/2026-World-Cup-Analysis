"""
app/utils/charts.py
────────────────────
Reusable Plotly chart builders.
All charts return a go.Figure so pages control layout/sizing.
"""
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# ── Colour palette ────────────────────────────────────────────────────────────
PRIMARY   = "#00A86B"    # FIFA green
SECONDARY = "#1A1A2E"    # dark navy
ACCENT    = "#E8C547"    # gold
TEXT      = "#FAFAFA"
GREY      = "#8B8FA8"
BG        = "#0F0F23"


def standings_bar(df: pd.DataFrame, group: str) -> go.Figure:
    """
    Horizontal bar chart of points for a single group.
    df must have: team_name, points, goals_for, goals_against, won, drawn, lost
    """
    gdf = df[df["group_name"] == group].sort_values("points", ascending=True)

    fig = go.Figure(go.Bar(
        y=gdf["team_name"],
        x=gdf["points"],
        orientation="h",
        marker_color=PRIMARY,
        text=gdf["points"],
        textposition="outside",
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Points: %{x}<br>"
            "GF: %{customdata[0]}  GA: %{customdata[1]}<br>"
            "W/D/L: %{customdata[2]}/%{customdata[3]}/%{customdata[4]}"
            "<extra></extra>"
        ),
        customdata=gdf[["goals_for", "goals_against", "won", "drawn", "lost"]].values,
    ))
    fig.update_layout(
        title=f"Group {group} Standings",
        xaxis_title="Points",
        plot_bgcolor=BG, paper_bgcolor=BG,
        font_color=TEXT,
        height=280,
        margin=dict(l=10, r=30, t=40, b=20),
    )
    return fig


def top_scorers_bar(df: pd.DataFrame, n: int = 10) -> go.Figure:
    """Horizontal bar chart of top scorers."""
    df = df.head(n).sort_values("goals", ascending=True)
    fig = go.Figure(go.Bar(
        y=df["player_name"],
        x=df["goals"],
        orientation="h",
        marker_color=ACCENT,
        text=df["goals"],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>Goals: %{x}<extra></extra>",
    ))
    fig.update_layout(
        title=f"Top {n} Scorers",
        plot_bgcolor=BG, paper_bgcolor=BG,
        font_color=TEXT,
        height=max(300, n * 30),
        margin=dict(l=10, r=30, t=40, b=20),
    )
    return fig


def player_radar(player_row: pd.Series, label: str = "") -> go.Figure:
    """
    Spider/radar chart for a single player's normalised per-90 stats.
    player_row must contain: goals_p90, assists_p90, xg_p90,
    xa_p90, pressures_p90, progressive_passes_p90
    """
    categories = ["Goals/90", "Assists/90", "xG/90", "xA/90",
                  "Pressures/90", "Prog Passes/90"]
    keys = ["goals_p90", "assists_p90", "xg_p90",
            "xa_p90", "pressures_p90", "progressive_passes_p90"]

    values = [float(player_row.get(k, 0)) for k in keys]

    fig = go.Figure(go.Scatterpolar(
        r=values + [values[0]],
        theta=categories + [categories[0]],
        fill="toself",
        fillcolor=f"rgba(0, 168, 107, 0.35)",
        line=dict(color=PRIMARY, width=2),
        name=label or str(player_row.get("player_name", "")),
    ))
    fig.update_layout(
        polar=dict(
            bgcolor=SECONDARY,
            radialaxis=dict(visible=True, showticklabels=False),
            angularaxis=dict(tickfont=dict(size=11, color=TEXT)),
        ),
        plot_bgcolor=BG, paper_bgcolor=BG,
        font_color=TEXT,
        showlegend=False,
        height=380,
        margin=dict(l=30, r=30, t=30, b=30),
    )
    return fig


def win_probability_gauge(home_prob: float, draw_prob: float, away_prob: float,
                           home_name: str, away_name: str) -> go.Figure:
    """
    Stacked horizontal bar showing win/draw/loss probability.
    Probabilities should sum to 1.0.
    """
    fig = go.Figure()

    fig.add_trace(go.Bar(
        name=f"{home_name} Win",
        x=[home_prob * 100],
        y=["Probability"],
        orientation="h",
        marker_color=PRIMARY,
        text=f"{home_prob*100:.1f}%",
        textposition="inside",
        textfont=dict(color="white", size=14),
    ))
    fig.add_trace(go.Bar(
        name="Draw",
        x=[draw_prob * 100],
        y=["Probability"],
        orientation="h",
        marker_color=GREY,
        text=f"{draw_prob*100:.1f}%",
        textposition="inside",
        textfont=dict(color="white", size=14),
    ))
    fig.add_trace(go.Bar(
        name=f"{away_name} Win",
        x=[away_prob * 100],
        y=["Probability"],
        orientation="h",
        marker_color=ACCENT,
        text=f"{away_prob*100:.1f}%",
        textposition="inside",
        textfont=dict(color="white", size=14),
    ))

    fig.update_layout(
        barmode="stack",
        xaxis=dict(range=[0, 100], showticklabels=False),
        yaxis=dict(showticklabels=False),
        plot_bgcolor=BG, paper_bgcolor=BG,
        font_color=TEXT,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=160,
        margin=dict(l=10, r=10, t=10, b=10),
    )
    return fig


def xg_scatter(df: pd.DataFrame) -> go.Figure:
    """
    Scatter plot: xG vs Actual Goals per team.
    Points above the diagonal = over-performed; below = under-performed.
    """
    fig = go.Figure()

    # Diagonal reference line
    max_val = max(df["xg"].max(), df["goals_for"].max(), 0.1) * 1.1
    fig.add_trace(go.Scatter(
        x=[0, max_val], y=[0, max_val],
        mode="lines",
        line=dict(color=GREY, dash="dash", width=1),
        showlegend=False,
        hoverinfo="skip",
    ))

    fig.add_trace(go.Scatter(
        x=df["xg"],
        y=df["goals_for"],
        mode="markers+text",
        text=df["team_name"],
        textposition="top center",
        marker=dict(size=10, color=PRIMARY, opacity=0.85),
        hovertemplate="<b>%{text}</b><br>xG: %{x:.2f}<br>Goals: %{y}<extra></extra>",
    ))

    fig.update_layout(
        title="xG vs Actual Goals — Tournament Performance",
        xaxis_title="Expected Goals (xG)",
        yaxis_title="Actual Goals Scored",
        plot_bgcolor=BG, paper_bgcolor=BG,
        font_color=TEXT,
        height=420,
        margin=dict(l=10, r=10, t=50, b=40),
    )
    return fig


def cpcs_scatter(df: pd.DataFrame) -> go.Figure:
    """
    Scatter: CPCS score vs minutes played.
    Top-right = stars; top-left = undervalued.
    """
    color_map = {"FWD": "#E74C3C", "MID": "#3498DB", "DEF": "#2ECC71", "GK": "#F39C12"}
    df = df.copy()
    df["color"] = df["position_group"].map(color_map).fillna(GREY)

    fig = go.Figure(go.Scatter(
        x=df["minutes_played"],
        y=df["cpcs"],
        mode="markers",
        text=df["player_name"],
        marker=dict(size=8, color=df["color"], opacity=0.8),
        hovertemplate=(
            "<b>%{text}</b><br>"
            "CPCS: %{y:.1f}<br>"
            "Minutes: %{x}<br>"
            "<extra></extra>"
        ),
    ))

    # Quadrant annotations
    mid_x = df["minutes_played"].median()
    mid_y = df["cpcs"].median()
    fig.add_annotation(x=mid_x * 0.5,  y=df["cpcs"].max() * 0.9, text="⭐ Undervalued",  showarrow=False, font=dict(color=ACCENT, size=11))
    fig.add_annotation(x=df["minutes_played"].max() * 0.75, y=df["cpcs"].max() * 0.9, text="🌟 Stars", showarrow=False, font=dict(color=ACCENT, size=11))

    fig.update_layout(
        title="Player Contribution Score vs Minutes Played",
        xaxis_title="Minutes Played",
        yaxis_title="CPCS (0–100)",
        plot_bgcolor=BG, paper_bgcolor=BG,
        font_color=TEXT,
        height=500,
        margin=dict(l=10, r=10, t=50, b=40),
    )
    return fig

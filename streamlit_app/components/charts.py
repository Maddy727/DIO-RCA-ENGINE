"""
charts.py

Reusable plotly chart builders. Every chart here consumes already-computed
dataframes (from dio_aggregation.py / aggregations.py) — no business logic,
no new metrics, just visualization.

Two real formatting bugs fixed here (found and confirmed, not guessed):
  1. Decimal/cut-off labels: texttemplate was "%{text:£,.0f}" — Plotly's
     d3-format mini-language does not recognize '£' as a valid symbol
     INSIDE the format spec, so the whole format silently failed and fell
     back to raw unrounded floats (explaining both the decimals AND the
     cut-off labels, since raw floats are much wider text). Fixed by
     moving '£' OUTSIDE the placeholder: "£%{text:,.0f}".
  2. Legend overlap: legend was pinned to y=1.02 (just above the plot
     canvas) with no reserved space, colliding with the section header
     above it. Fixed by moving legends below the plot area instead.
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from .styling import CHART_PALETTE

BAR_COLOR = CHART_PALETTE["primary"]
EXCESS_COLOR = CHART_PALETTE["accent_red"]
PROBLEM_AREA_COLORS = CHART_PALETTE["problem_area"]
CHART_FONT = dict(family="Segoe UI, Arial, sans-serif", size=13, color="#101828")


def _base_layout(fig: go.Figure, height: int = 360, legend_below: bool = True) -> go.Figure:
    legend_cfg = dict(orientation="h", yanchor="top", y=-0.18, xanchor="left", x=0) if legend_below else dict()
    fig.update_layout(
        font=CHART_FONT,
        margin=dict(l=10, r=60, t=40, b=10),
        height=height,
        plot_bgcolor="white",
        paper_bgcolor="white",
        legend=legend_cfg,
        title_font=dict(size=14, color="#101828"),
    )
    fig.update_xaxes(automargin=True)
    fig.update_yaxes(automargin=True)
    return fig


def _currency_texttemplate() -> str:
    # '£' MUST sit outside the {} placeholder — see module docstring bug #1.
    return "£%{text:,.0f}"


def _plain_texttemplate() -> str:
    return "%{text:,.1f}"


def ranked_bar(df: pd.DataFrame, x: str, y: str, title: str = "", horizontal: bool = True,
               color: str = BAR_COLOR, currency: bool = True, top_n: int | None = None) -> go.Figure:
    df = df.sort_values(x, ascending=False)
    if top_n:
        df = df.head(top_n)
    df = df.sort_values(x, ascending=horizontal)

    texttemplate = _currency_texttemplate() if currency else _plain_texttemplate()

    if horizontal:
        fig = px.bar(df, x=x, y=y, orientation="h", title=title,
                     color_discrete_sequence=[color], text=x)
        max_val = df[x].max()
        fig.update_xaxes(range=[0, max_val * 1.22])
    else:
        fig = px.bar(df, x=y, y=x, title=title, color_discrete_sequence=[color], text=x)
    fig.update_traces(texttemplate=texttemplate, textposition="outside", cliponaxis=False)
    return _base_layout(fig)


def dio_variance_bar(df: pd.DataFrame, category_col: str, title: str = "",
                      top_n: int | None = 10, metric_col: str = "DIO_Variance",
                      value_suffix: str = "d", allow_negative_color: bool = True) -> go.Figure:
    """
    Single-metric ranked bar chart (per Design_Inspiration-5): one bar per
    entity, sorted descending by metric_col, color intensity scaling with
    magnitude rather than a flat color. Defaults to DIO_Variance (Enterprise/
    CSCO usage — positive variance in red tones, negative in green).

    Also used for Regional's "rank by highest DIO" chart (metric_col="DIO",
    allow_negative_color=False — DIO is never negative, so the whole scale
    runs red-intensity by magnitude rather than diverging at zero).
    """
    df = df.sort_values(metric_col, ascending=False)
    if top_n:
        df = df.head(top_n)
    df = df.sort_values(metric_col, ascending=True)

    scale = CHART_PALETTE["variance_scale"]
    max_val_for_color = max(df[metric_col].max(), 1e-9)

    def _color_for(v):
        if allow_negative_color and v <= 0:
            return CHART_PALETTE["secondary"]
        idx = min(int((v / max_val_for_color) * (len(scale) - 1)), max(len(scale) - 1, 0))
        idx = max(idx, 0)
        return scale[idx]

    colors = [_color_for(v) for v in df[metric_col]]

    texttemplate = f"%{{text:+.1f}}{value_suffix}" if allow_negative_color else f"%{{text:.1f}}{value_suffix}"

    fig = go.Figure(go.Bar(
        x=df[metric_col], y=df[category_col], orientation="h",
        marker_color=colors, text=df[metric_col],
        texttemplate=texttemplate, textposition="outside", cliponaxis=False,
    ))
    max_val = df[metric_col].max()
    min_val = min(df[metric_col].min(), 0) if allow_negative_color else 0
    fig.update_xaxes(range=[min_val * 1.1 if min_val < 0 else 0, max_val * 1.25],
                      title=f"{metric_col.replace('_', ' ')} ({'days' if value_suffix == 'd' else ''})")
    fig.update_layout(title=title, showlegend=False)
    return _base_layout(fig, height=max(300, 34 * len(df)))


def dio_vs_target_bar(df: pd.DataFrame, category_col: str, title: str = "") -> go.Figure:
    """Grouped bar: DIO vs DIO_Target. Retained for detail-level comparisons;
    DIO Variance is now the primary chart style per your confirmed decision."""
    df = df.sort_values("DIO", ascending=True)
    fig = go.Figure()
    fig.add_trace(go.Bar(y=df[category_col], x=df["DIO"], name="DIO (actual)",
                          orientation="h", marker_color=BAR_COLOR))
    fig.add_trace(go.Bar(y=df[category_col], x=df["DIO_Target"], name="DIO Target",
                          orientation="h", marker_color=CHART_PALETTE["neutral"]))
    fig.update_layout(barmode="group", title=title)
    return _base_layout(fig, height=max(300, 30 * len(df)))


def problem_area_donut(df: pd.DataFrame, title: str = "RCA Problem Area Split") -> go.Figure:
    colors = [PROBLEM_AREA_COLORS.get(pa, CHART_PALETTE["neutral"]) for pa in df["Problem_Area"]]
    fig = go.Figure(data=[go.Pie(
        labels=df["Problem_Area"], values=df["Count"], hole=0.55,
        marker=dict(colors=colors), textinfo="label+percent",
    )])
    fig.update_layout(title=title)
    return _base_layout(fig)


def actions_required_donut(df: pd.DataFrame, title: str = "Actions Required — SKU Count") -> go.Figure:
    """Donut of Store_Action_Recommendation counts, matching Design_Inspiration-5's
    'Actions Required' pairing with the Top 10 SKUs by DIO Variance chart."""
    palette = [CHART_PALETTE["accent_red"], CHART_PALETTE["secondary"], CHART_PALETTE["accent_amber"],
               CHART_PALETTE["neutral"], CHART_PALETTE["primary"], CHART_PALETTE["primary_light"]]
    colors = [palette[i % len(palette)] for i in range(len(df))]
    fig = go.Figure(data=[go.Pie(
        labels=df["Store_Action_Recommendation"], values=df["Count"], hole=0.55,
        marker=dict(colors=colors), textinfo="percent",
    )])
    fig.update_layout(title=title)
    return _base_layout(fig)


def heatmap(pivot_df: pd.DataFrame, title: str = "Category x Problem Area",
            colorbar_title: str = "Count of SKUs") -> go.Figure:
    fig = go.Figure(data=go.Heatmap(
        z=pivot_df.values, x=list(pivot_df.columns), y=list(pivot_df.index),
        colorscale="Reds", showscale=True,
        colorbar=dict(title=dict(text=colorbar_title, side="right")),
    ))
    fig.update_layout(title=title)
    return _base_layout(fig, height=max(300, 32 * len(pivot_df)), legend_below=False)

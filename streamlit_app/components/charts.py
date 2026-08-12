"""
charts.py

Reusable plotly chart builders. Every chart here consumes already-computed
dataframes (from dio_aggregation.py / aggregations.py) — no business logic,
no new metrics, just visualization.
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

BAR_COLOR = "#0B5AA8"
EXCESS_COLOR = "#B00020"
PROBLEM_AREA_COLORS = {
    "Demand": "#0B5AA8",
    "Supply": "#B36A00",
    "Network": "#1B6B3A",
    "Others": "#98A2B3",
}
CHART_FONT = dict(family="Segoe UI, Arial, sans-serif", size=13, color="#101828")


def _base_layout(fig: go.Figure, height: int = 360) -> go.Figure:
    fig.update_layout(
        font=CHART_FONT,
        margin=dict(l=10, r=10, t=30, b=10),
        height=height,
        plot_bgcolor="white",
        paper_bgcolor="white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    return fig


def ranked_bar(df: pd.DataFrame, x: str, y: str, title: str = "", horizontal: bool = True,
               color: str = BAR_COLOR, value_format: str = "£,.0f") -> go.Figure:
    df = df.sort_values(x, ascending=horizontal)
    if horizontal:
        fig = px.bar(df, x=x, y=y, orientation="h", title=title,
                     color_discrete_sequence=[color], text=x)
    else:
        fig = px.bar(df, x=y, y=x, title=title, color_discrete_sequence=[color], text=x)
    fig.update_traces(texttemplate=f"%{{text:{value_format}}}", textposition="outside")
    return _base_layout(fig)


def dio_vs_target_bar(df: pd.DataFrame, category_col: str, title: str = "") -> go.Figure:
    """Grouped bar: DIO vs DIO_Target per category_col (Store_ID, Category, etc.)."""
    df = df.sort_values("DIO", ascending=True)
    fig = go.Figure()
    fig.add_trace(go.Bar(y=df[category_col], x=df["DIO"], name="DIO (actual)",
                          orientation="h", marker_color=BAR_COLOR))
    fig.add_trace(go.Bar(y=df[category_col], x=df["DIO_Target"], name="DIO Target",
                          orientation="h", marker_color="#D0D5DD"))
    fig.update_layout(barmode="group", title=title)
    return _base_layout(fig, height=max(300, 28 * len(df)))


def problem_area_donut(df: pd.DataFrame, title: str = "RCA Problem Area Split") -> go.Figure:
    colors = [PROBLEM_AREA_COLORS.get(pa, "#98A2B3") for pa in df["Problem_Area"]]
    fig = go.Figure(data=[go.Pie(
        labels=df["Problem_Area"], values=df["Count"], hole=0.55,
        marker=dict(colors=colors), textinfo="label+percent",
    )])
    fig.update_layout(title=title)
    return _base_layout(fig)


def heatmap(pivot_df: pd.DataFrame, title: str = "Category x Problem Area") -> go.Figure:
    fig = go.Figure(data=go.Heatmap(
        z=pivot_df.values, x=list(pivot_df.columns), y=list(pivot_df.index),
        colorscale="Reds", showscale=True,
    ))
    fig.update_layout(title=title)
    return _base_layout(fig, height=max(300, 32 * len(pivot_df)))

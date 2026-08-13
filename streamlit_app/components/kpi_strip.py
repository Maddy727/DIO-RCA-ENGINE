"""
kpi_strip.py

Common KPI strip: DIO | DIO Target | DIO Variance | Total Inventory Value |
Excess Inventory Value, plus optional extra persona-specific KPI cards
appended after it. Used by all four pages so the core numbers are always
computed the same way (via dio_aggregation.py), regardless of which
persona is looking or what scope they're looking at.

DIO Variance is now an explicit common card (per instruction #13: "DIO,
DIO Target, DIO Variance, Total Inventory Value, Excess Inventory Value"
as the minimum set on every page, not just Enterprise).
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.dio_aggregation import rollup
from components.styling import format_gbp, format_days, format_variance_days


def render_kpi_strip(scoped_df: pd.DataFrame, extra_kpis: list[tuple[str, str, str]] | None = None):
    """
    scoped_df: a DIO-field-enriched wide dataframe already filtered to the
    scope this page/level represents (enterprise-wide, one region, one
    store, or a filtered slice).
    extra_kpis: optional list of (label, value, sub) tuples for
    persona-specific cards, rendered on a second row beneath the 5 common
    cards (keeps each row readable on a 16:9 screen instead of cramming
    everything into one wide row).
    """
    agg = rollup(scoped_df).iloc[0]

    common_cards = [
        ("DIO", format_days(agg["DIO"]), "value-weighted"),
        ("DIO Target", format_days(agg["DIO_Target"]), "value-weighted"),
        ("DIO Variance", format_variance_days(agg["DIO_Variance"]), "vs target"),
        ("Total Inventory Value", format_gbp(agg["Inventory_Value"]), None),
        ("Excess Inventory Value", format_gbp(agg["Excess_Value"]), None),
    ]
    _render_row(common_cards, primary=True)

    if extra_kpis:
        st.markdown('<div style="height:10px;"></div>', unsafe_allow_html=True)
        _render_row(extra_kpis)


def _render_row(cards: list[tuple[str, str, str]], primary: bool = False):
    cols = st.columns(len(cards))
    css_class = "kpi-card kpi-primary" if primary else "kpi-card"
    for col, (label, value, sub) in zip(cols, cards):
        with col:
            sub_html = f'<div class="kpi-sub">{sub}</div>' if sub else ""
            st.markdown(
                f"""
                <div class="{css_class}">
                    <div class="kpi-label">{label}</div>
                    <div class="kpi-value">{value}</div>
                    {sub_html}
                </div>
                """,
                unsafe_allow_html=True,
            )

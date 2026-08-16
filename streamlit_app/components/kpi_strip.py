"""
kpi_strip.py

Common KPI strip, restructured 2026-08-15 per your instruction: Row 1 is
always DIO | DIO Target | DIO Variance (3 cards). Row 2 is Total Inventory
Value | Excess Inventory Value, followed by any page-specific extra KPIs
(so a page with 1 extra KPI gets a clean row of 3, matching Store
Manager's and CSCO's explicit request — "SKUs Requiring Action" /
"SKU-Stores Assigned" no longer sits alone in its own sparse row).

This is now the single layout used by all four pages — Enterprise's 3
extras and Regional's 2 extras naturally fall in behind the same Row 2
pattern without needing page-specific special-casing.
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
    persona-specific cards, appended after Total/Excess Inventory Value
    on row 2.
    """
    agg = rollup(scoped_df).iloc[0]

    row1 = [
        ("DIO", format_days(agg["DIO"]), "value-weighted"),
        ("DIO Target", format_days(agg["DIO_Target"]), "value-weighted"),
        ("DIO Variance", format_variance_days(agg["DIO_Variance"]), "vs target"),
    ]
    row2 = [
        ("Total Inventory Value", format_gbp(agg["Inventory_Value"]), None),
        ("Excess Inventory Value", format_gbp(agg["Excess_Value"]), None),
    ]
    if extra_kpis:
        row2 = row2 + extra_kpis

    _render_row(row1, primary=True)
    st.markdown('<div style="height:10px;"></div>', unsafe_allow_html=True)
    _render_row(row2, primary=True)


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

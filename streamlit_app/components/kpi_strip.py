"""
kpi_strip.py

Common KPI strip, restructured 2026-08-15 per your instruction: Row 1 is
always DIO | DIO Target | DIO Variance (3 cards). Row 2 is Total Inventory
Value | Excess Inventory Value, followed by any page-specific extra KPIs
(so a page with 1 extra KPI gets a clean row of 3, matching Store
Manager's and CSCO's explicit request — "SKUs Requiring Action" /
"SKU-Stores Assigned" no longer sits alone in its own sparse row).

Enterprise Control Tower is the ONE confirmed exception (2026-08-15):
that page alone reverts to the original 5-then-3 layout (all 5 common
cards in row 1, its 3 extra KPIs in row 2) via five_in_first_row=True —
you were clear this should NOT apply to the other 3 pages.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.dio_aggregation import rollup
from components.styling import format_gbp, format_days, format_variance_days


def render_kpi_strip(scoped_df: pd.DataFrame, extra_kpis: list[tuple[str, str, str]] | None = None,
                      five_in_first_row: bool = False):
    """
    scoped_df: a DIO-field-enriched wide dataframe already filtered to the
    scope this page/level represents (enterprise-wide, one region, one
    store, or a filtered slice).
    extra_kpis: optional list of (label, value, sub) tuples for
    persona-specific cards, appended after Total/Excess Inventory Value.
    five_in_first_row: Enterprise-only override — puts all 5 common cards
    in row 1 and only extra_kpis in row 2, instead of the 3-then-rest
    layout used everywhere else.
    """
    agg = rollup(scoped_df).iloc[0]

    dio_cards = [
        ("DIO", format_days(agg["DIO"]), "value-weighted"),
        ("DIO Target", format_days(agg["DIO_Target"]), "value-weighted"),
        ("DIO Variance", format_variance_days(agg["DIO_Variance"]), "vs target"),
    ]
    value_cards = [
        ("Total Inventory Value", format_gbp(agg["Inventory_Value"]), None),
        ("Excess Inventory Value", format_gbp(agg["Excess_Value"]), None),
    ]

    if five_in_first_row:
        row1 = dio_cards + value_cards
        row2 = extra_kpis or []
    else:
        row1 = dio_cards
        row2 = value_cards + (extra_kpis or [])

    _render_row(row1, primary=True)
    if row2:
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

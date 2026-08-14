"""
drilldown.py

One reusable drill-down implementation. Each persona page calls this with
its OWN level sequence (e.g. Enterprise page: Region->Store->Category->SKU;
Regional page, already region-scoped: Store->Category->SKU; CSCO page,
already category-scoped on entry: Region->Store->SKU) and a root_label for
the breadcrumb. The underlying mechanics (breadcrumb, KPI re-scoping,
click-to-drill, SKU detail hand-off) are identical everywhere — only the
level sequence and starting scope differ per persona, matching each
persona's confirmed entry altitude.

Uses Streamlit session_state to persist the current drill-down path across
reruns within a page.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.dio_aggregation import rollup
from components.kpi_strip import render_kpi_strip
from components.tables import render_table
from components.sku_detail import render_sku_detail

LEVEL_GROUP_COL = {"Region": "Region", "Store": "Store_Name", "Category": "Category"}


def _state_key(namespace: str) -> str:
    return f"drilldown_path_{namespace}"


def render_drilldown(namespace: str, scoped_wide: pd.DataFrame, rca_long: pd.DataFrame,
                      corrective_action_long: pd.DataFrame, levels: list[str], root_label: str):
    """
    namespace: unique per-page key prefix so each page keeps independent state.
    scoped_wide: the wide dataframe ALREADY filtered to this persona's
                 starting scope (e.g. one region for Regional Manager),
                 already DIO-enriched (dio_aggregation.add_dio_fields applied).
    levels: the sequence of drill-down levels FROM the entry point down to
            SKU, e.g. ["Store", "Category", "SKU"].
    root_label: breadcrumb label for the starting scope, e.g. "Region: North"
                or "Enterprise" or "Category: BWS".
    """
    key = _state_key(namespace)
    if key not in st.session_state:
        st.session_state[key] = []  # list of (level_name, value) tuples, in `levels` order

    path = st.session_state[key]

    crumbs = [root_label] + [str(v) for _, v in path]
    col_bc, col_reset = st.columns([6, 1])
    with col_bc:
        st.markdown(f"**{'  ›  '.join(crumbs)}**")
    with col_reset:
        if path and st.button("Reset", key=f"{namespace}_reset"):
            st.session_state[key] = []
            st.rerun()

    scoped = scoped_wide.copy()
    for level_name, value in path:
        col = LEVEL_GROUP_COL.get(level_name, level_name)
        scoped = scoped[scoped[col] == value]

    render_kpi_strip(scoped)
    st.markdown("<br>", unsafe_allow_html=True)

    depth = len(path)

    if depth >= len(levels) or levels[depth] == "SKU":
        _render_sku_list_and_detail(namespace, scoped, scoped_wide, rca_long, corrective_action_long)
        return

    next_level = levels[depth]
    group_col = LEVEL_GROUP_COL.get(next_level, next_level)
    if group_col not in scoped.columns:
        st.info(f"No '{next_level}' breakdown available at this scope.")
        return

    table = rollup(scoped, group_col).sort_values("DIO", ascending=False)
    st.markdown(f"**{next_level} breakdown** ({len(table)})")
    selected = render_table(
        table, gbp_cols=["Inventory_Value", "Excess_Value"], day_cols=["DIO", "DIO_Target"],
        key=f"{namespace}_level_table_{depth}", selectable=True,
    )
    if selected is not None:
        st.session_state[key] = path + [(next_level, selected[group_col])]
        st.rerun()


def _render_sku_list_and_detail(namespace, scoped, full_wide, rca_long, corrective_action_long):
    from utils.aggregations import summarize_root_causes, add_shelf_life_display

    summary = summarize_root_causes(rca_long)
    sku_summary = scoped.merge(summary, on=["SKU_ID", "Store_ID"], how="left")
    sku_summary = add_shelf_life_display(sku_summary)
    sku_summary = sku_summary[[
        "SKU_ID", "SKU_Name", "Category", "Store_Name", "Root_Cause_Summary",
        "DIO", "DIO_Target", "Shelf_Life_Display", "Excess_Value", "Priority_Score",
    ]].sort_values("Priority_Score", ascending=False)

    st.markdown(f"**{len(sku_summary)} SKU-Store(s) in scope**")
    selected = render_table(sku_summary, gbp_cols=["Excess_Value"], day_cols=["DIO", "DIO_Target"],
                             key=f"{namespace}_sku_table", selectable=True)
    if selected is not None:
        st.markdown("---")
        store_id = scoped[scoped["SKU_ID"] == selected["SKU_ID"]]["Store_ID"].iloc[0]
        render_sku_detail(selected["SKU_ID"], store_id, full_wide, rca_long, corrective_action_long)

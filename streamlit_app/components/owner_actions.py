"""
owner_actions.py

The "Action Owner" section on the CSCO page: lets a Central-team
stakeholder (Demand Planner, Replenishment Planner, Buyer, Network
Planner) or Store Manager filter the estate down to exactly the actions
assigned to them.

Journey: Owner picker -> KPI strip (population-scoped, de-duplicated,
clearly labelled as non-additive across owners) -> region-wise summary ->
drill to Store -> root-cause-grain Action Items list (never merges
multiple root causes into one row) -> click a row to open full SKU Detail.

Design decisions confirmed with you 2026-08-14:
  - Population scoping (de-duplicated by SKU-Store) for KPIs/region
    summary — NOT additive across owners, by design, since a SKU-Store
    can have causes owned by multiple different people.
  - Root-cause-grain Action Items list for the final drill-down level —
    one row per actual action, matching the RCA Details tab's existing
    "shown separately, never merged" convention. Excess_Value shown on
    every row for context (kept sortable — can't hide it on "repeat"
    rows since that would break with arbitrary column sorting), with an
    explicit caption warning against summing it.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.dio_aggregation import rollup
from utils.aggregations import owner_scoped_sku_store_keys, owner_action_items
from utils.priority_labels import TABLE_TEXT_COLORS
from components.kpi_strip import render_kpi_strip
from components.tables import render_table
from components.sku_detail import render_sku_detail
from components.styling import empty_state_message, dio_variance_color

OWNERS = ["Demand Planner", "Replenishment Planner", "Buyer", "Network Planner", "Store Manager"]


def render_owner_action_center(wide: pd.DataFrame, corrective_action_long: pd.DataFrame,
                                rca_long: pd.DataFrame, master: pd.DataFrame, financial: pd.DataFrame):
    owner = st.selectbox("Action Owner", OWNERS, key="csco_owner")

    scoped_keys = owner_scoped_sku_store_keys(corrective_action_long, owner)
    if scoped_keys.empty:
        empty_state_message()
        return

    owner_wide = wide.merge(scoped_keys, on=["SKU_ID", "Store_ID"], how="inner")

    st.caption(
        f"Showing SKU-Stores with at least one open action owned by **{owner}**. "
        "These figures are NOT additive across owners — a SKU-Store with causes "
        "owned by multiple people will appear (with its full Excess Value) under "
        "each of them."
    )
    render_kpi_strip(owner_wide, extra_kpis=[("SKU-Stores Assigned", f"{len(owner_wide):,}", None)])

    # ---- Region-wise summary ----
    st.markdown('<div class="section-header">Region-wise Summary</div>', unsafe_allow_html=True)
    by_region = rollup(owner_wide, "Region")
    render_table(
        by_region[["Region", "DIO", "DIO_Target", "DIO_Variance", "Inventory_Value", "Excess_Value", "SKU_Store_Count"]],
        gbp_cols=["Inventory_Value", "Excess_Value"], day_cols=["DIO", "DIO_Target", "DIO_Variance"],
        text_color_cols={"DIO_Variance": dio_variance_color},
    )

    # ---- Drill: Region -> Store -> Action Items ----
    st.markdown('<div class="section-header">Drill Down: Region → Store → Action Items</div>', unsafe_allow_html=True)
    regions = sorted(owner_wide["Region"].dropna().unique().tolist())
    region = st.selectbox("Region", regions, key="csco_owner_region")
    region_scoped = owner_wide[owner_wide["Region"] == region]

    stores = sorted(region_scoped["Store_Name"].dropna().unique().tolist())
    store_name = st.selectbox("Store", stores, key="csco_owner_store")
    store_scoped_keys = region_scoped[region_scoped["Store_Name"] == store_name][["SKU_ID", "Store_ID"]]

    items = owner_action_items(corrective_action_long, master, financial, wide, owner)
    items = items.merge(store_scoped_keys, on=["SKU_ID", "Store_ID"], how="inner")

    if items.empty:
        empty_state_message()
        return

    st.markdown(f"**{len(items)} action item(s)** for {owner} at {store_name}")
    st.caption(
        "Excess_Value is SKU-Store-level context, not a per-action amount — if the "
        "same SKU-Store has multiple root causes below, the same figure appears on "
        "each row. Do not sum this column."
    )
    selected = render_table(
        items[["SKU_ID", "SKU_Name", "Category", "Root_Cause", "Corrective_Action",
               "Priority_Label", "Priority_Score", "Excess_Value", "Review_Owner"]],
        gbp_cols=["Excess_Value"], key="csco_owner_action_items", selectable=True,
        text_color_cols={"Priority_Label": lambda v: TABLE_TEXT_COLORS.get(v)},
    )
    if selected is not None:
        st.markdown("---")
        store_id = store_scoped_keys[store_scoped_keys["SKU_ID"] == selected["SKU_ID"]]["Store_ID"].iloc[0]
        render_sku_detail(selected["SKU_ID"], store_id, wide, rca_long, corrective_action_long)

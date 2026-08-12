"""
task_cards.py

Store Manager Daily Task Cards. Groups are built from the EXISTING,
already-validated Store_Action_Recommendation values (store_action_output)
and the Path_Taken field — nothing here is a new business rule, it's a
presentation-layer regrouping of engine output text.

The "For Visibility — Not Your Action" strip surfaces root causes whose
Dashboard_View does not include "Store" (i.e. Central-owned: Demand
Planner / Replenishment Planner / Buyer), honestly labelled with their
real owner rather than presented as a Store Manager task.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.priority_labels import priority_label, LABEL_COLORS, LABEL_ORDER
from utils.aggregations import dashboard_view_filter
from components.styling import format_gbp, priority_badge_html

TASK_GROUP_DEFINITIONS = [
    {
        "title": "Perishable Expiry Risk",
        "icon": "🍎",
        "match": lambda df: df["Path_Taken"] == "Perishable",
        "color": "#B00020",
        "cta": "DO NOW",
    },
    {
        "title": "Recount Required",
        "icon": "🔢",
        "match": lambda df: df["Store_Action_Recommendation"] == "Recounting of SKU Required",
        "color": "#B00020",
        "cta": "DO TODAY",
    },
    {
        "title": "Transfer Viable",
        "icon": "🚚",
        "match": lambda df: df["Store_Action_Recommendation"] == "Transfer Viable - Check with Network Planner and Execute",
        "color": "#B36A00",
        "cta": "THIS WEEK",
    },
    {
        "title": "Markdown Recommended",
        "icon": "🏷️",
        "match": lambda df: df["Store_Action_Recommendation"] == "Markdown can be considered - check with Commercial Team and Execute",
        "color": "#B36A00",
        "cta": "THIS WEEK",
    },
    {
        "title": "Transfer / Markdown / Do-Nothing Decision",
        "icon": "🤔",
        "match": lambda df: df["Store_Action_Recommendation"] == "To decide among Transfer to distant Store or Markdown or Do-nothing",
        "color": "#B36A00",
        "cta": "THIS WEEK",
    },
    {
        "title": "Monitor — Post-Promo",
        "icon": "👀",
        "match": lambda df: df["Store_Action_Recommendation"].str.contains(
            "monitor post-promo velocity", case=False, na=False
        ),
        "color": "#0B5AA8",
        "cta": "MONITOR",
    },
]


def render_task_cards(scoped_wide: pd.DataFrame, namespace: str = "sm_tasks"):
    """
    scoped_wide: wide dataframe already filtered to ONE store (and DIO-
    enriched with Priority_Label added). Renders task cards; returns the
    selected group title (or None) so the caller can render the drill-down
    for that group beneath.
    """
    selected_group = None
    any_task = False

    for group in TASK_GROUP_DEFINITIONS:
        mask = group["match"](scoped_wide)
        subset = scoped_wide[mask]
        if subset.empty:
            continue
        any_task = True

        n_skus = len(subset)
        excess_value = subset["Excess_Value"].sum()
        top_label = _highest_priority_label(subset)

        with st.container():
            st.markdown(
                f"""
                <div style="border-left:5px solid {group['color']}; background:#FAFAFA;
                            border-radius:6px; padding:12px 16px; margin-bottom:10px;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div style="font-weight:700; font-size:15px;">
                            {group['icon']} {group['title'].upper()}
                        </div>
                        {priority_badge_html(top_label, LABEL_COLORS[top_label])}
                    </div>
                    <div style="margin-top:6px; color:#475467; font-size:13px;">
                        <span style="background:{group['color']}; color:white; padding:1px 8px;
                                     border-radius:4px; font-size:11px; font-weight:700; margin-right:8px;">
                            {group['cta']}
                        </span>
                        {n_skus} SKU-Store(s) &nbsp;·&nbsp; {format_gbp(excess_value)} at stake
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button(f"View {group['title']}", key=f"{namespace}_{group['title']}"):
                selected_group = group["title"]

    if not any_task:
        st.success("No active tasks for this store today.")

    return selected_group


def render_fyi_strip(scoped_wide: pd.DataFrame, corrective_action_long: pd.DataFrame):
    """
    Root causes NOT owned by the Store Manager (Dashboard_View doesn't
    include 'Store'). Shown for visibility only, honestly attributed to
    their real owner — per your confirmed decision, not a 6th task card.
    """
    store_skus = scoped_wide[["SKU_ID", "Store_ID", "Excess_Value"]]
    ca_for_store = corrective_action_long.merge(store_skus, on=["SKU_ID", "Store_ID"], how="inner")
    central_only = dashboard_view_filter(ca_for_store, "Central")
    # Exclude anything that's ALSO tagged Store (i.e. keep pure-Central rows only,
    # since Store+Regional rows are already covered by the task cards above)
    central_only = central_only[~central_only["Dashboard_View"].str.contains("Store", case=False, na=False)]

    if central_only.empty:
        return

    by_owner = (
        central_only.drop_duplicates(subset=["SKU_ID", "Store_ID", "Action_Owner"])
        .groupby("Action_Owner")
        .agg(SKU_Store_Count=("SKU_ID", "count"), Excess_Value=("Excess_Value", "sum"))
        .reset_index()
        .sort_values("Excess_Value", ascending=False)
    )

    st.markdown(
        f"""
        <div class="fyi-strip">
            <div class="fyi-title">For Visibility — Not Your Action</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(
        "These SKUs also have open issues, but the corrective action belongs to central "
        "planning roles, not the Store Manager."
    )
    st.dataframe(
        by_owner.assign(Excess_Value=by_owner["Excess_Value"].apply(format_gbp)),
        width='stretch', hide_index=True,
    )


def _highest_priority_label(subset: pd.DataFrame) -> str:
    labels = subset["Priority_Score"].apply(priority_label)
    for lbl in LABEL_ORDER:  # ordered Emergency..Low
        if (labels == lbl).any():
            return lbl
    return "Low"

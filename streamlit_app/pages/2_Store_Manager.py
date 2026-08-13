"""
pages/2_Store_Manager.py — Store Manager view

"What do I need to do today?"

Daily Task Cards are the PRIMARY interface. Page order (per your instruction
#22): actions the Store Manager owns -> recommended action -> SKU/action
detail -> supporting analytics -> "For Visibility — Not Your Action" LAST.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st

from utils.data_loader import load_all
from utils.dio_aggregation import add_dio_fields
from utils.priority_labels import add_priority_label
from utils.aggregations import summarize_root_causes, top_skus_by_dio_variance, actions_required_sku_count
from components.styling import inject_base_css, persona_banner, brand_strip, PERSONA_COLORS, empty_state_message
from components.kpi_strip import render_kpi_strip
from components.charts import dio_variance_bar, actions_required_donut
from components.filters import render_filter_panel
from components.tables import render_table
from components.sku_detail import render_sku_detail
from components.task_cards import render_task_cards, render_fyi_strip, TASK_GROUP_DEFINITIONS

st.set_page_config(page_title="Tesco DIO Control Tower — Store Manager", layout="wide", page_icon="🏪")
inject_base_css()
brand_strip()

try:
    data = load_all()
except FileNotFoundError as e:
    st.error(str(e))
    st.stop()

wide = add_dio_fields(data["wide"])
wide = add_priority_label(wide)
rca_long = data["rca_long"]
corrective_action_long = data["corrective_action_long"]

persona_banner("🏪 Store Manager", "What do I need to do today?", PERSONA_COLORS["store"])

stores = sorted(wide["Store_Name"].dropna().unique().tolist())
store_name = st.selectbox("Store", stores, key="sm_store")
store_scoped = wide[wide["Store_Name"] == store_name]

scoped = render_filter_panel(store_scoped, key_prefix="sm")

if scoped.empty:
    empty_state_message()
    st.stop()

# ---- KPI strip (kept compact — supporting context, not the focus) ----
n_requiring_action = scoped["Store_Action_Recommendation"].notna().sum()
extra_kpis = [("SKUs Requiring Action", f"{n_requiring_action:,}", None)]
render_kpi_strip(scoped, extra_kpis=extra_kpis)

# ---- 1. Daily Task Cards — what the Store Manager is responsible for ----
st.markdown('<div class="section-header">Daily Task Cards</div>', unsafe_allow_html=True)
st.caption(f"Store Manager Task View — {store_name}")

selected_group_key = "sm_selected_group"
clicked_group = render_task_cards(scoped, namespace="sm_tasks")
if clicked_group:
    st.session_state[selected_group_key] = clicked_group

# ---- 2/3. Task detail — recommended action + SKU/action details ----
if st.session_state.get(selected_group_key):
    group_title = st.session_state[selected_group_key]
    group_def = next((g for g in TASK_GROUP_DEFINITIONS if g["title"] == group_title), None)
    if group_def:
        st.markdown(f'<div class="section-header">Task: {group_title}</div>', unsafe_allow_html=True)
        group_skus = scoped[group_def["match"](scoped)]
        summary = summarize_root_causes(rca_long)
        group_skus = group_skus.merge(summary, on=["SKU_ID", "Store_ID"], how="left")

        st.markdown("**SKUs in this task**")
        selected = render_table(
            group_skus[["SKU_ID", "SKU_Name", "Category", "Root_Cause_Summary",
                        "Priority_Score", "Priority_Label", "Excess_Value",
                        "Store_Action_Recommendation"]],
            gbp_cols=["Excess_Value"], key="sm_task_detail_table", selectable=True,
        )
        if selected is not None:
            st.markdown("---")
            store_id = scoped[scoped["SKU_ID"] == selected["SKU_ID"]]["Store_ID"].iloc[0]
            render_sku_detail(selected["SKU_ID"], store_id, wide, rca_long, corrective_action_long)

    if st.button("Close task detail"):
        st.session_state[selected_group_key] = None
        st.rerun()

st.markdown("---")

# ---- 4. Supporting information: full Action Queue ----
st.markdown('<div class="section-header">Action Queue — All SKUs, Sorted by Priority</div>', unsafe_allow_html=True)
summary = summarize_root_causes(rca_long)
queue = scoped.merge(summary, on=["SKU_ID", "Store_ID"], how="left")
queue = queue[[
    "SKU_ID", "SKU_Name", "Category", "Root_Cause_Summary", "Priority_Score", "Priority_Label",
    "Urgency_Score", "DIO", "Excess_Units", "Excess_Value", "Store_Action_Recommendation",
]].sort_values("Priority_Score", ascending=False)

selected_from_queue = render_table(
    queue, gbp_cols=["Excess_Value"], day_cols=["DIO"], key="sm_action_queue", selectable=True,
)
if selected_from_queue is not None:
    st.markdown("---")
    store_id = scoped[scoped["SKU_ID"] == selected_from_queue["SKU_ID"]]["Store_ID"].iloc[0]
    render_sku_detail(selected_from_queue["SKU_ID"], store_id, wide, rca_long, corrective_action_long)

# ---- Supporting information: Top 10 SKUs by DIO Variance + Actions Required (new, per your approval) ----
st.markdown('<div class="section-header">Top 10 SKUs by DIO Variance &amp; Actions Required</div>', unsafe_allow_html=True)
c1, c2 = st.columns(2)
with c1:
    top_skus = top_skus_by_dio_variance(scoped, 10)
    if top_skus.empty:
        empty_state_message()
    else:
        st.plotly_chart(dio_variance_bar(top_skus, "SKU_Name", top_n=None), width="stretch")
with c2:
    actions = actions_required_sku_count(scoped)
    if actions.empty:
        empty_state_message()
    else:
        st.plotly_chart(actions_required_donut(actions), width="stretch")

# ---- LAST: "For Visibility — Not Your Action" (per your instruction #22 — always at the bottom) ----
render_fyi_strip(scoped, corrective_action_long)

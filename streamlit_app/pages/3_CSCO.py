"""
pages/3_CSCO.py — Head of Planning / CSCO view

"Which categories and structural issues are driving DIO across the estate?"
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st

from utils.data_loader import load_all
from utils.dio_aggregation import add_dio_fields, rollup
from utils.priority_labels import add_priority_label
from utils.aggregations import (
    problem_area_split, owner_accountability, category_x_problem_area,
    top_skus_by_dio_variance, actions_required_sku_count,
)
from components.styling import inject_base_css, persona_banner, brand_strip, PERSONA_COLORS, empty_state_message
from components.kpi_strip import render_kpi_strip
from components.charts import dio_variance_bar, ranked_bar, problem_area_donut, heatmap, actions_required_donut
from components.filters import render_filter_panel
from components.drilldown import render_drilldown
from components.owner_actions import render_owner_action_center

st.set_page_config(page_title="Tesco DIO Control Tower — Head of Planning / CSCO", layout="wide", page_icon="📊")
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

persona_banner(
    "📊 Head of Planning / CSCO",
    "Which categories are driving DIO and excess inventory across the estate?",
    PERSONA_COLORS["csco"],
)

filtered = render_filter_panel(wide, key_prefix="csco")

if filtered.empty:
    empty_state_message()
    st.stop()

# ---- KPI strip ----
extra_kpis = [
    ("Affected Stores", f"{filtered['Store_ID'].nunique():,}", None),
    ("Affected Categories", f"{filtered['Category'].nunique():,}", None),
]
render_kpi_strip(filtered, extra_kpis=extra_kpis)

by_category = rollup(filtered, "Category")

st.markdown('<div class="section-header">DIO Variance by Category</div>', unsafe_allow_html=True)
st.plotly_chart(dio_variance_bar(by_category, "Category", top_n=None), width="stretch")

st.markdown('<div class="section-header">Inventory Value &amp; Excess Inventory Value by Category</div>',
            unsafe_allow_html=True)
c1, c2 = st.columns(2)
with c1:
    st.plotly_chart(ranked_bar(by_category, "Inventory_Value", "Category", "Inventory Value by Category"), width="stretch")
with c2:
    st.plotly_chart(ranked_bar(by_category, "Excess_Value", "Category", "Excess Value by Category", color="#C81E3A"), width="stretch")

st.markdown('<div class="section-header">RCA Problem Area &amp; Corrective Action Ownership</div>',
            unsafe_allow_html=True)
c1, c2 = st.columns(2)
with c1:
    rca_scoped = rca_long.merge(filtered[["SKU_ID", "Store_ID"]], on=["SKU_ID", "Store_ID"], how="inner")
    st.plotly_chart(problem_area_donut(problem_area_split(rca_scoped)), width="stretch")
with c2:
    ca_scoped = corrective_action_long.merge(filtered[["SKU_ID", "Store_ID"]], on=["SKU_ID", "Store_ID"], how="inner")
    owners = owner_accountability(ca_scoped, filtered)
    st.plotly_chart(ranked_bar(owners, "Excess_Value", "Action_Owner", "Excess Value by Action Owner", color="#1B6B3A"), width="stretch")

# ---- Top 10 SKUs by DIO Variance + Actions Required (new, per your approval) ----
st.markdown('<div class="section-header">Top 10 SKUs by DIO Variance &amp; Actions Required</div>', unsafe_allow_html=True)
c1, c2 = st.columns(2)
with c1:
    top_skus = top_skus_by_dio_variance(filtered, 10)
    if top_skus.empty:
        empty_state_message()
    else:
        st.plotly_chart(dio_variance_bar(top_skus, "SKU_Name", top_n=None), width="stretch")
with c2:
    actions = actions_required_sku_count(filtered)
    if actions.empty:
        empty_state_message()
    else:
        st.plotly_chart(actions_required_donut(actions), width="stretch")

st.markdown('<div class="section-header">Category × Problem Area — Where DIO Problems Concentrate</div>',
            unsafe_allow_html=True)
rca_scoped_all = rca_long.merge(filtered[["SKU_ID", "Store_ID"]], on=["SKU_ID", "Store_ID"], how="inner")
pivot = category_x_problem_area(rca_scoped_all, data["master"])
if pivot.empty:
    empty_state_message()
else:
    st.plotly_chart(heatmap(pivot, "Category × Problem Area", colorbar_title="Count of SKUs"), width="stretch")

st.markdown('<div class="section-header">Drill Down: Category → Region → Store → SKU</div>', unsafe_allow_html=True)
categories = sorted(filtered["Category"].dropna().unique().tolist())
if not categories:
    empty_state_message()
else:
    category = st.selectbox("Category", categories, key="csco_category")
    scoped = filtered[filtered["Category"] == category]
    render_drilldown(
        namespace="csco", scoped_wide=scoped, rca_long=rca_long,
        corrective_action_long=corrective_action_long,
        levels=["Region", "Store", "SKU"], root_label=f"Category: {category}",
    )

st.markdown("---")
st.caption(
    "Store-level ranking is intentionally not shown until you drill into a category, "
    "per the CSCO's strategic (not store-operational) view."
)

# ---- Action Owner View — for Central team members to find their assigned actions ----
st.markdown("---")
st.markdown('<div class="section-header">🎯 Action Owner View — Find Your Assigned Actions</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="section-subtext">For Demand Planners, Replenishment Planners, Buyers, and Network '
    'Planners on the Central Team: filter to your own name to see exactly what\'s been assigned to '
    'you, region by region, down to the individual action.</div>',
    unsafe_allow_html=True,
)
render_owner_action_center(wide, corrective_action_long, rca_long, data["master"], data["financial"])

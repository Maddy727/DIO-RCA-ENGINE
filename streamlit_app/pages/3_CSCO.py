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
from utils.aggregations import problem_area_split, owner_accountability, category_x_problem_area
from components.styling import inject_base_css, persona_banner, format_gbp, PERSONA_COLORS
from components.kpi_strip import render_kpi_strip
from components.charts import dio_vs_target_bar, ranked_bar, problem_area_donut, heatmap
from components.drilldown import render_drilldown

st.set_page_config(page_title="DIO Control Tower — Head of Planning / CSCO", layout="wide", page_icon="📊")
inject_base_css()

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

# ---- KPI strip ----
extra_kpis = [
    ("Affected Stores", f"{wide['Store_ID'].nunique():,}", None),
    ("Affected Categories", f"{wide['Category'].nunique():,}", None),
]
render_kpi_strip(wide, extra_kpis=extra_kpis)

by_category = rollup(wide, "Category")

st.markdown('<div class="section-header">DIO by Category</div>', unsafe_allow_html=True)
st.plotly_chart(dio_vs_target_bar(by_category, "Category", ""), width='stretch')

st.markdown('<div class="section-header">Inventory Value by Category &nbsp;&nbsp;|&nbsp;&nbsp; Excess Inventory Value by Category</div>',
            unsafe_allow_html=True)
c1, c2 = st.columns(2)
with c1:
    st.plotly_chart(ranked_bar(by_category, "Inventory_Value", "Category", ""), width='stretch')
with c2:
    st.plotly_chart(ranked_bar(by_category, "Excess_Value", "Category", "", color="#B00020"),
                     width='stretch')

st.markdown('<div class="section-header">RCA Problem Area &nbsp;&nbsp;|&nbsp;&nbsp; Corrective Action Ownership</div>',
            unsafe_allow_html=True)
c1, c2 = st.columns(2)
with c1:
    st.plotly_chart(problem_area_donut(problem_area_split(rca_long)), width='stretch')
with c2:
    owners = owner_accountability(corrective_action_long, wide)
    st.plotly_chart(
        ranked_bar(owners, "Excess_Value", "Action_Owner", "", color="#1B6B3A"),
        width='stretch',
    )

st.markdown('<div class="section-header">Category × Problem Area — Where DIO Problems Concentrate</div>',
            unsafe_allow_html=True)
pivot = category_x_problem_area(rca_long, data["master"])
st.plotly_chart(heatmap(pivot, ""), width='stretch')

st.markdown('<div class="section-header">Drill Down: Category → Region → Store → SKU</div>', unsafe_allow_html=True)
categories = sorted(wide["Category"].dropna().unique().tolist())
category = st.selectbox("Category", categories, key="csco_category")
scoped = wide[wide["Category"] == category]
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

"""
app.py — Enterprise Control Tower (landing page)

DOES NOT run the RCA engine, Store Action, Priority, or any business logic.
Reads pre-generated outputs (data/outputs/*.csv) plus Sample_RCA_Data.xlsx
and Financial_Impact_Data.xlsx via utils/data_loader.py, and presents them.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st

from utils.data_loader import load_all
from utils.dio_aggregation import add_dio_fields, rollup
from utils.priority_labels import add_priority_label
from utils.aggregations import problem_area_split, owner_accountability
from components.styling import inject_base_css, persona_banner, format_gbp, PERSONA_COLORS
from components.kpi_strip import render_kpi_strip
from components.charts import dio_vs_target_bar, ranked_bar, problem_area_donut
from components.filters import render_filter_panel
from components.drilldown import render_drilldown

st.set_page_config(page_title="DIO Control Tower — Enterprise", layout="wide", page_icon="🏢")
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
    "🏢 Enterprise Control Tower",
    "Where is our DIO problem, and where should leadership focus?",
    PERSONA_COLORS["enterprise"],
)

filtered = render_filter_panel(wide, key_prefix="ent")

# ---- KPI strip ----
enterprise_agg = rollup(filtered).iloc[0]
extra_kpis = [
    ("SKU-Stores Requiring Intervention", f"{len(filtered):,}", None),
    ("Stores with DIO Issue", f"{filtered['Store_ID'].nunique():,}", None),
    ("Categories with DIO Issue", f"{filtered['Category'].nunique():,}", None),
]
render_kpi_strip(filtered, extra_kpis=extra_kpis)

st.markdown('<div class="section-header">A. DIO by Store</div>', unsafe_allow_html=True)
by_store = rollup(filtered, "Store_ID").merge(
    wide[["Store_ID", "Store_Name"]].drop_duplicates(), on="Store_ID", how="left"
)
c1, c2 = st.columns([3, 2])
with c1:
    st.plotly_chart(dio_vs_target_bar(by_store, "Store_Name", "DIO vs Target by Store"),
                     width='stretch')
with c2:
    st.dataframe(
        by_store[["Store_Name", "DIO", "DIO_Target", "DIO_Variance", "Inventory_Value",
                  "Excess_Value", "SKU_Store_Count"]]
        .assign(
            Inventory_Value=lambda d: d["Inventory_Value"].apply(format_gbp),
            Excess_Value=lambda d: d["Excess_Value"].apply(format_gbp),
        )
        .sort_values("DIO_Variance", ascending=False),
        width='stretch', hide_index=True, height=340,
    )

st.markdown('<div class="section-header">B. DIO by Category</div>', unsafe_allow_html=True)
by_category = rollup(filtered, "Category")
c1, c2 = st.columns([3, 2])
with c1:
    st.plotly_chart(dio_vs_target_bar(by_category, "Category", "DIO vs Target by Category"),
                     width='stretch')
with c2:
    st.dataframe(
        by_category.assign(
            Inventory_Value=lambda d: d["Inventory_Value"].apply(format_gbp),
            Excess_Value=lambda d: d["Excess_Value"].apply(format_gbp),
        ).sort_values("DIO_Variance", ascending=False),
        width='stretch', hide_index=True, height=340,
    )

st.markdown('<div class="section-header">C. Inventory Value by Category</div>', unsafe_allow_html=True)
c1, c2 = st.columns(2)
with c1:
    st.plotly_chart(
        ranked_bar(by_category, "Inventory_Value", "Category", "Total Inventory Value (£)"),
        width='stretch',
    )
with c2:
    st.markdown('<div class="section-header" style="margin-top:0;">D. Excess Inventory Value by Category</div>',
                unsafe_allow_html=True)
    st.plotly_chart(
        ranked_bar(by_category, "Excess_Value", "Category", "Excess Inventory Value (£)", color="#B00020"),
        width='stretch',
    )

st.markdown('<div class="section-header">E. RCA Problem Area Split &nbsp;&nbsp;|&nbsp;&nbsp; F. Action Owner Accountability</div>',
            unsafe_allow_html=True)
c1, c2 = st.columns(2)
with c1:
    rca_scoped = rca_long[rca_long.set_index(["SKU_ID", "Store_ID"]).index.isin(
        filtered.set_index(["SKU_ID", "Store_ID"]).index
    )]
    st.plotly_chart(problem_area_donut(problem_area_split(rca_scoped)), width='stretch')
with c2:
    ca_scoped = corrective_action_long[corrective_action_long.set_index(["SKU_ID", "Store_ID"]).index.isin(
        filtered.set_index(["SKU_ID", "Store_ID"]).index
    )]
    owners = owner_accountability(ca_scoped, filtered)
    st.plotly_chart(
        ranked_bar(owners, "Excess_Value", "Action_Owner", "Excess Value by Action Owner", color="#1B2A4A"),
        width='stretch',
    )

st.markdown('<div class="section-header">Drill Down: Enterprise → Region → Store → Category → SKU</div>',
            unsafe_allow_html=True)
render_drilldown(
    namespace="enterprise", scoped_wide=filtered, rca_long=rca_long,
    corrective_action_long=corrective_action_long,
    levels=["Region", "Store", "Category", "SKU"], root_label="Enterprise",
)

st.markdown("---")
st.caption(
    "DIO is a value-weighted aggregate (Total Inventory Value ÷ Total imputed Daily COGS), "
    "not a simple average — see README for methodology. No historical/weekly data exists in "
    "the current dataset, so trend views are not shown in V1."
)

"""
pages/1_Regional_Manager.py — Regional Manager view

"Which stores need my attention/coaching this week?"
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st

from utils.data_loader import load_all
from utils.dio_aggregation import add_dio_fields, rollup
from utils.priority_labels import add_priority_label, LABEL_ORDER
from utils.aggregations import problem_area_split
from components.styling import inject_base_css, persona_banner, format_gbp, PERSONA_COLORS
from components.kpi_strip import render_kpi_strip
from components.charts import dio_vs_target_bar, ranked_bar, problem_area_donut
from components.drilldown import render_drilldown

st.set_page_config(page_title="DIO Control Tower — Regional Manager", layout="wide", page_icon="🌍")
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
    "🌍 Regional Manager",
    "Which stores need my attention / coaching this week?",
    PERSONA_COLORS["regional"],
)

regions = sorted(wide["Region"].dropna().unique().tolist())
region = st.selectbox("Region", regions, key="rm_region")
scoped = wide[wide["Region"] == region]

# ---- KPI strip ----
stores_requiring = scoped[scoped["Store_Action_Recommendation"].notna()]["Store_ID"].nunique()
extra_kpis = [
    ("Stores Requiring Intervention", f"{stores_requiring:,}", None),
    ("SKU-Stores Requiring Intervention", f"{len(scoped):,}", None),
]
render_kpi_strip(scoped, extra_kpis=extra_kpis)

st.markdown('<div class="section-header">Store DIO Ranking vs Target</div>', unsafe_allow_html=True)
by_store = rollup(scoped, "Store_ID").merge(
    wide[["Store_ID", "Store_Name"]].drop_duplicates(), on="Store_ID", how="left"
)
c1, c2 = st.columns([3, 2])
with c1:
    st.plotly_chart(dio_vs_target_bar(by_store, "Store_Name", ""), width='stretch')
with c2:
    priority_counts = (
        scoped.groupby("Store_Name")["Priority_Label"]
        .apply(lambda s: (s.isin(["Emergency", "Urgent"])).sum())
        .reset_index(name="High_Priority_Actions")
    )
    display = by_store.merge(priority_counts, on="Store_Name", how="left")
    st.dataframe(
        display[["Store_Name", "DIO", "DIO_Target", "DIO_Variance", "Excess_Value",
                  "SKU_Store_Count", "High_Priority_Actions"]]
        .assign(Excess_Value=lambda d: d["Excess_Value"].apply(format_gbp))
        .sort_values("DIO_Variance", ascending=False),
        width='stretch', hide_index=True, height=340,
    )

st.markdown('<div class="section-header">Inventory Value & Excess Value by Store</div>', unsafe_allow_html=True)
c1, c2 = st.columns(2)
with c1:
    st.plotly_chart(ranked_bar(by_store, "Inventory_Value", "Store_Name", "Inventory Value (£)"),
                     width='stretch')
with c2:
    st.plotly_chart(ranked_bar(by_store, "Excess_Value", "Store_Name", "Excess Value (£)", color="#B00020"),
                     width='stretch')

st.markdown('<div class="section-header">RCA Problem Area Split &nbsp;&nbsp;|&nbsp;&nbsp; Top Categories Contributing to Excess Value</div>',
            unsafe_allow_html=True)
c1, c2 = st.columns(2)
with c1:
    rca_scoped = rca_long[rca_long.set_index(["SKU_ID", "Store_ID"]).index.isin(
        scoped.set_index(["SKU_ID", "Store_ID"]).index
    )]
    st.plotly_chart(problem_area_donut(problem_area_split(rca_scoped)), width='stretch')
with c2:
    by_cat = rollup(scoped, "Category").sort_values("Excess_Value", ascending=False).head(8)
    st.plotly_chart(ranked_bar(by_cat, "Excess_Value", "Category", "", color="#B36A00"),
                     width='stretch')

st.markdown('<div class="section-header">4-Week Trend</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="fyi-strip"><div class="fyi-title">Placeholder — Future Enhancement</div>'
    'Historical trend requires weekly snapshot data — not available in V1. '
    'No trend figures are fabricated.</div>',
    unsafe_allow_html=True,
)

st.markdown('<div class="section-header">Drill Down: Store → Category → SKU</div>', unsafe_allow_html=True)
render_drilldown(
    namespace="regional", scoped_wide=scoped, rca_long=rca_long,
    corrective_action_long=corrective_action_long,
    levels=["Store", "Category", "SKU"], root_label=f"Region: {region}",
)

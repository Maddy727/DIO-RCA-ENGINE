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
from utils.priority_labels import add_priority_label
from utils.aggregations import problem_area_split, top_skus_by_dio_variance, actions_required_sku_count
from components.styling import inject_base_css, persona_banner, brand_strip, PERSONA_COLORS, empty_state_message, dio_variance_color
from components.kpi_strip import render_kpi_strip
from components.charts import dio_variance_bar, ranked_bar, problem_area_donut, actions_required_donut
from components.filters import render_filter_panel
from components.tables import render_table, add_rank_column
from components.see_more import see_more_toggle
from components.drilldown import render_drilldown

st.set_page_config(page_title="Tesco DIO Control Tower — Regional Manager", layout="wide", page_icon="🌍")
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
    "🌍 Regional Manager",
    "Which stores need my attention / coaching this week?",
    PERSONA_COLORS["regional"],
)

regions = sorted(wide["Region"].dropna().unique().tolist())
region = st.selectbox("Region", regions, key="rm_region")
region_scoped = wide[wide["Region"] == region]

scoped = render_filter_panel(region_scoped, key_prefix="rm")

if scoped.empty:
    empty_state_message()
    st.stop()

# ---- KPI strip ----
stores_requiring = scoped[scoped["Store_Action_Recommendation"].notna()]["Store_ID"].nunique()
extra_kpis = [
    ("Stores Requiring Intervention", f"{stores_requiring:,}", None),
    ("SKU-Stores Requiring Intervention", f"{len(scoped):,}", None),
]
render_kpi_strip(scoped, extra_kpis=extra_kpis)

# ---- Store DIO Ranking (by HIGHEST DIO, per instruction #10) ----
st.markdown('<div class="section-header">Store DIO Ranking</div>', unsafe_allow_html=True)
st.markdown('<div class="section-subtext">Ranked by highest DIO — Rank 1 is the store with the most inventory coverage relative to sales.</div>', unsafe_allow_html=True)
by_store = rollup(scoped, "Store_ID").merge(
    wide[["Store_ID", "Store_Name"]].drop_duplicates(), on="Store_ID", how="left"
)
top_n = see_more_toggle("rm_store_dio", default_n=10)

priority_counts = (
    scoped.groupby("Store_Name")["Priority_Label"]
    .apply(lambda s: (s.isin(["Emergency", "Urgent"])).sum())
    .reset_index(name="High_Priority_Actions")
)
store_table = by_store.merge(priority_counts, on="Store_Name", how="left")
store_table_full = add_rank_column(store_table, "DIO", ascending=False)
store_table_capped = store_table_full.head(top_n) if top_n else store_table_full

render_table(
    store_table_capped[["Rank", "Store_Name", "DIO", "DIO_Target", "DIO_Variance", "Excess_Value",
                         "SKU_Store_Count", "High_Priority_Actions"]],
    gbp_cols=["Excess_Value"], day_cols=["DIO", "DIO_Target", "DIO_Variance"], height=340,
    text_color_cols={"DIO_Variance": dio_variance_color},
)

st.markdown('<div style="height:14px;"></div>', unsafe_allow_html=True)
c1, c2 = st.columns(2)
with c1:
    st.plotly_chart(
        dio_variance_bar(store_table_capped, "Store_Name", title="Store DIO Ranking", top_n=None,
                          metric_col="DIO", allow_negative_color=False),
        width="stretch",
    )
with c2:
    by_cat_variance = rollup(scoped, "Category")
    st.plotly_chart(
        dio_variance_bar(by_cat_variance, "Category", title="Categories vs DIO Variance", top_n=None),
        width="stretch",
    )

# ---- Inventory Value & Excess Value by Store ----
st.markdown('<div class="section-header">Inventory Value &amp; Excess Value by Store</div>', unsafe_allow_html=True)
c1, c2 = st.columns(2)
with c1:
    st.plotly_chart(ranked_bar(by_store, "Inventory_Value", "Store_Name", "Inventory Value (£)"), width="stretch")
with c2:
    st.plotly_chart(ranked_bar(by_store, "Excess_Value", "Store_Name", "Excess Value (£)", color="#C81E3A"), width="stretch")

# ---- Problem Area & Top Categories ----
st.markdown('<div class="section-header">RCA Problem Area Split &amp; Top Categories by Excess Value</div>',
            unsafe_allow_html=True)
c1, c2 = st.columns(2)
with c1:
    rca_scoped = rca_long.merge(scoped[["SKU_ID", "Store_ID"]], on=["SKU_ID", "Store_ID"], how="inner")
    st.plotly_chart(problem_area_donut(problem_area_split(rca_scoped)), width="stretch")
with c2:
    by_cat = rollup(scoped, "Category").sort_values("Excess_Value", ascending=False).head(8)
    st.plotly_chart(ranked_bar(by_cat, "Excess_Value", "Category", "Top Categories by Excess Value", color="#D97B0A"), width="stretch")

# ---- Top 10 SKUs by DIO Variance + Actions Required (new, per your approval) ----
st.markdown('<div class="section-header">SKUs by DIO Variance &amp; Actions Required</div>', unsafe_allow_html=True)
c1, c2 = st.columns(2)
with c1:
    top_skus = top_skus_by_dio_variance(scoped, 10)
    if top_skus.empty:
        empty_state_message()
    else:
        st.plotly_chart(dio_variance_bar(top_skus, "SKU_Name", title="Top 10 SKUs – DIO Variance", top_n=None), width="stretch")
with c2:
    actions = actions_required_sku_count(scoped)
    if actions.empty:
        empty_state_message()
    else:
        st.plotly_chart(actions_required_donut(actions), width="stretch")

# ---- 4-Week Trend placeholder ----
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

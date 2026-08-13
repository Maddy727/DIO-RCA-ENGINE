"""
views/enterprise.py — Enterprise Control Tower content

DOES NOT run the RCA engine, Store Action, Priority, or any business logic.
Reads pre-generated outputs (data/outputs/*.csv) plus Sample_RCA_Data.xlsx
and Financial_Impact_Data.xlsx via utils/data_loader.py, and presents them.

Routed to as "Command Centre" in the sidebar via app.py's st.navigation()
— kept as a separate content file (rather than being app.py itself) so
app.py can stay a thin router without changing your existing Streamlit
Cloud "Main file path" setting (still streamlit_app/app.py).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st

from utils.data_loader import load_all
from utils.dio_aggregation import add_dio_fields, rollup
from utils.priority_labels import add_priority_label
from utils.aggregations import problem_area_split, owner_accountability
from components.styling import inject_base_css, persona_banner, brand_strip, format_gbp, PERSONA_COLORS, empty_state_message
from components.kpi_strip import render_kpi_strip
from components.charts import dio_variance_bar, ranked_bar, problem_area_donut
from components.filters import render_filter_panel
from components.tables import render_table, add_rank_column
from components.see_more import see_more_toggle
from components.drilldown import render_drilldown

st.set_page_config(page_title="Tesco DIO Control Tower — Command Centre", layout="wide", page_icon="🏢")
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
    "🏢 Enterprise Control Tower",
    "Where is our DIO problem, and where should leadership focus?",
    PERSONA_COLORS["enterprise"],
)

filtered = render_filter_panel(wide, key_prefix="ent")

if filtered.empty:
    empty_state_message()
    st.stop()

extra_kpis = [
    ("SKU-Stores Requiring Intervention", f"{len(filtered):,}", None),
    ("Stores with DIO Issue", f"{filtered['Store_ID'].nunique():,}", None),
    ("Categories with DIO Issue", f"{filtered['Category'].nunique():,}", None),
]
render_kpi_strip(filtered, extra_kpis=extra_kpis)

# ---- A. DIO Variance by Store ----
st.markdown('<div class="section-header">DIO Variance by Store</div>', unsafe_allow_html=True)
st.markdown('<div class="section-subtext">Where inventory coverage most exceeds target — the primary story for leadership focus.</div>', unsafe_allow_html=True)
by_store = rollup(filtered, "Store_ID").merge(
    wide[["Store_ID", "Store_Name"]].drop_duplicates(), on="Store_ID", how="left"
)
top_n = see_more_toggle("ent_store_dio", default_n=10)
c1, c2 = st.columns([3, 2])
with c1:
    st.plotly_chart(dio_variance_bar(by_store, "Store_Name", top_n=top_n), width="stretch")
with c2:
    store_table = add_rank_column(by_store, "DIO_Variance", ascending=False)
    render_table(
        store_table[["Rank", "Store_Name", "DIO", "DIO_Target", "DIO_Variance", "Inventory_Value",
                     "Excess_Value", "SKU_Store_Count"]],
        gbp_cols=["Inventory_Value", "Excess_Value"], day_cols=["DIO", "DIO_Target", "DIO_Variance"],
        height=340,
    )

# ---- B. DIO Variance by Category ----
st.markdown('<div class="section-header">DIO Variance by Category</div>', unsafe_allow_html=True)
by_category = rollup(filtered, "Category")
c1, c2 = st.columns([3, 2])
with c1:
    st.plotly_chart(dio_variance_bar(by_category, "Category", top_n=None), width="stretch")
with c2:
    cat_table = add_rank_column(by_category, "DIO_Variance", ascending=False)
    render_table(
        cat_table[["Rank", "Category", "DIO", "DIO_Target", "DIO_Variance", "Inventory_Value",
                   "Excess_Value", "SKU_Store_Count"]],
        gbp_cols=["Inventory_Value", "Excess_Value"], day_cols=["DIO", "DIO_Target", "DIO_Variance"],
        height=340,
    )

# ---- C/D. Inventory Value & Excess Value by Category ----
st.markdown('<div class="section-header">Inventory Value & Excess Inventory Value by Category</div>', unsafe_allow_html=True)
c1, c2 = st.columns(2)
with c1:
    st.plotly_chart(
        ranked_bar(by_category, "Inventory_Value", "Category", "Total Inventory Value (£)"),
        width="stretch",
    )
with c2:
    st.plotly_chart(
        ranked_bar(by_category, "Excess_Value", "Category", "Excess Inventory Value (£)", color="#C81E3A"),
        width="stretch",
    )

# ---- E/F. Problem Area & Owner Accountability ----
st.markdown('<div class="section-header">RCA Problem Area Split &amp; Action Owner Accountability</div>',
            unsafe_allow_html=True)
c1, c2 = st.columns(2)
with c1:
    rca_scoped = rca_long.merge(filtered[["SKU_ID", "Store_ID"]], on=["SKU_ID", "Store_ID"], how="inner")
    st.plotly_chart(problem_area_donut(problem_area_split(rca_scoped)), width="stretch")
with c2:
    ca_scoped = corrective_action_long.merge(filtered[["SKU_ID", "Store_ID"]], on=["SKU_ID", "Store_ID"], how="inner")
    owners = owner_accountability(ca_scoped, filtered)
    st.plotly_chart(
        ranked_bar(owners, "Excess_Value", "Action_Owner", "Excess Value by Action Owner", color="#1B2A4A"),
        width="stretch",
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

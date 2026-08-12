"""
sku_detail.py

Shared SKU Detail view: RCA Details / Signals / Actions / Priority tabs,
plus financial context. Used by every persona's drill-down — one
implementation, reused everywhere, per the architecture spec.

Every root cause for the SKU-Store is shown as a SEPARATE row in the RCA
Details tab — never merged. The "+N more" summary only ever appears in
list/queue views (see aggregations.summarize_root_causes), not here.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.priority_labels import priority_label, normalize_priority_pct, LABEL_COLORS
from components.styling import format_gbp, format_days, priority_badge_html

SIGNAL_COLUMNS = [c for c in [
    "S01_Weeks_Cover", "S01_Weeks_Cover_Target", "S02_Zero_Sales_Flag", "S03_Active_Promo_Flag",
    "S04_Upcoming_Promo_Flag", "S04_Days_To_Promo_Start", "S05_Promo_Stock_Ordered_Flag",
    "S06_Days_Since_Promo_Ended", "S07_Post_Promo_Velocity_Ratio", "S08_Active_Season_Flag",
    "S09_Days_To_Season_End", "S10_Sales_Velocity_Ratio", "S11_Peer_Active_Promo_Flag",
    "S12_Peer_DIO_Rate", "S13_Format_DIO_Ratio", "S14_Peer_Shortage_Flag",
    "S15_Forecast_vs_Actual_Pct", "S16_Par_Level_Age_Days", "S17_Excess_Supply_Ratio",
    "S18_Promo_Excess_Supply_Ratio", "S19_High_SS_Flag_Days", "S20_Supplier_MOQ_Ratio",
    "S21_Is_Perishable", "S22_Shelf_Life_Remaining_Days",
]]


def render_sku_detail(sku_id: str, store_id: str, wide: pd.DataFrame,
                       rca_long: pd.DataFrame, corrective_action_long: pd.DataFrame):
    row = wide[(wide["SKU_ID"] == sku_id) & (wide["Store_ID"] == store_id)]
    if row.empty:
        st.warning("No data found for this SKU-Store.")
        return
    row = row.iloc[0]

    st.markdown(f"### {row['SKU_Name']}  ·  `{sku_id}`")
    st.caption(f"{row['Store_Name']} ({store_id})  ·  {row['Category']}  ·  {row['Region']}")

    label = priority_label(row["Priority_Score"])
    badge = priority_badge_html(label, LABEL_COLORS[label])
    st.markdown(
        f"{badge}&nbsp;&nbsp;Priority Score: **{row['Priority_Score']:.2f}** "
        f"({normalize_priority_pct(row['Priority_Score']):.0f}% of max)",
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("DIO", format_days(row["DIO"]) if "DIO" in row else format_days(row["S01_Weeks_Cover"] * 7))
    c2.metric("DIO Target", format_days(row["DIO_Target"]) if "DIO_Target" in row else format_days(row["S01_Weeks_Cover_Target"] * 7))
    c3.metric("Current Stock", f"{row['Current_Stock_Units']:,.0f} units")
    c4.metric("Excess Units", f"{row['Excess_Units']:,.0f} units")
    c5.metric("Excess Value", format_gbp(row["Excess_Value"]))

    tab_rca, tab_signals, tab_actions, tab_priority = st.tabs(
        ["RCA Details", "Signals", "Actions", "Priority"]
    )

    with tab_rca:
        findings = rca_long[(rca_long["SKU_ID"] == sku_id) & (rca_long["Store_ID"] == store_id)]
        st.markdown(f"**{len(findings)} root cause(s) fired for this SKU-Store** — shown separately, never merged.")
        display = findings[["Rule_ID", "Root_Cause", "Problem_Area", "Triggering_Signal",
                             "Signal_Value", "Threshold_Applied", "Gate_Status"]]
        st.dataframe(display, width='stretch', hide_index=True)

    with tab_signals:
        signal_df = pd.DataFrame({"Signal": SIGNAL_COLUMNS, "Value": [row[c] for c in SIGNAL_COLUMNS]})
        st.dataframe(signal_df, width='stretch', hide_index=True, height=400)

    with tab_actions:
        st.markdown("**Store Action (decision-support)**")
        st.info(row["Store_Action_Recommendation"])
        with st.expander("Decision path"):
            st.code(row["Decision_Path"])

        st.markdown("**Corrective Action(s) — one row per root cause, per owner**")
        ca = corrective_action_long[(corrective_action_long["SKU_ID"] == sku_id) & (corrective_action_long["Store_ID"] == store_id)]
        st.dataframe(
            ca[["Root_Cause", "Corrective_Action", "Action_Owner", "Review_Owner", "Dashboard_View"]],
            width='stretch', hide_index=True,
        )

        st.markdown("**Financial context**")
        f1, f2, f3 = st.columns(3)
        f1.metric("Unit Cost", format_gbp(row["Unit_Cost"]))
        f2.metric("Unit Price", format_gbp(row["Unit_Price"]))
        f3.metric("Gross Margin %", f"{row['Gross_Margin_Pct']*100:.1f}%")

    with tab_priority:
        p1, p2, p3, p4 = st.columns(4)
        p1.metric("Urgency Score", f"{row['Urgency_Score']:.0f} / 5")
        p2.metric("DIO Severity Score", f"{row['DIO_Severity_Score']:.0f} / 5")
        p3.metric("Margin Score", f"{row['Margin_Score']:.0f} / 5")
        p4.metric("Excess Value Score", f"{row['Excess_Value_Score']:.0f} / 5")
        margin_pct = row["Margin_Percentile_Within_Store"]
        excess_pct = row["Excess_Value_Percentile_Within_Store"]
        margin_pct_str = "n/a (small population fallback)" if pd.isna(margin_pct) else f"{margin_pct:.0f}%"
        excess_pct_str = "n/a (small population fallback)" if pd.isna(excess_pct) else f"{excess_pct:.0f}%"
        st.caption(
            f"Store eligible population: {row['Store_Eligible_Population_Size']:.0f} "
            f"| Margin percentile within store: {margin_pct_str}"
            f" | Excess Value percentile within store: {excess_pct_str}"
        )

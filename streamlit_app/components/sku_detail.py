"""
sku_detail.py

Shared SKU Detail view: RCA Details / Actions / Priority tabs, plus
financial context. Used by every persona's drill-down — one
implementation, reused everywhere, per the architecture spec.

Every root cause for the SKU-Store is shown as a SEPARATE row in the RCA
Details tab — never merged. The "+N more" summary only ever appears in
list/queue views (see aggregations.summarize_root_causes), not here.

Changes from the previous version (per your approved formatting corrections):
  - Signals tab removed (approved: no client-facing decision value, and
    benchmarking showed removing it wouldn't have improved performance
    anyway since it only ever rendered one row's 22 values).
  - Gate_Status column removed from the RCA Details table (always
    "gate_open" in practice for the display case — no client-facing
    signal). Display-only removal; the underlying engine output/CSV keeps
    the field.
  - Priority tab now also shows Priority Score and Priority Label
    (colour-coded, dot treatment) alongside the four existing sub-scores.
  - The "Store eligible population / percentile" debug caption is removed
    from the client-facing view.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.priority_labels import priority_label, normalize_priority_pct, LABEL_COLORS
from components.styling import format_gbp, format_days, priority_badge_html, priority_dot_label_html


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
    if pd.isna(row["Priority_Score"]):
        st.markdown(
            f"{badge}&nbsp;&nbsp;This SKU-Store is within target — no DIO intervention required, so it was never scored.",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"{badge}&nbsp;&nbsp;Priority Score: **{row['Priority_Score']:.2f}** "
            f"({normalize_priority_pct(row['Priority_Score']):.0f}% of max)",
            unsafe_allow_html=True,
        )

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("DIO", format_days(row["DIO"]))
    c2.metric("DIO Target", format_days(row["DIO_Target"]))
    c3.metric("Current Stock", f"{row['Current_Stock_Units']:,.0f} units")
    c4.metric("Excess Units", f"{row['Excess_Units']:,.0f} units")
    c5.metric("Excess Value", format_gbp(row["Excess_Value"]))

    tab_rca, tab_actions, tab_priority = st.tabs(["RCA Details", "Actions", "Priority"])

    with tab_rca:
        findings = rca_long[(rca_long["SKU_ID"] == sku_id) & (rca_long["Store_ID"] == store_id)]
        st.markdown(f"**{len(findings)} root cause(s) fired for this SKU-Store** — shown separately, never merged.")
        display = findings[["Rule_ID", "Root_Cause", "Problem_Area", "Triggering_Signal",
                             "Signal_Value", "Threshold_Applied"]]
        st.dataframe(display, width="stretch", hide_index=True)

    with tab_actions:
        st.markdown("**Store Action (decision-support)**")
        st.info(row["Store_Action_Recommendation"])
        with st.expander("Decision path"):
            st.code(row["Decision_Path"])

        st.markdown("**Corrective Action(s) — one row per root cause, per owner**")
        ca = corrective_action_long[(corrective_action_long["SKU_ID"] == sku_id) & (corrective_action_long["Store_ID"] == store_id)]
        st.dataframe(
            ca[["Root_Cause", "Corrective_Action", "Action_Owner", "Review_Owner", "Dashboard_View"]],
            width="stretch", hide_index=True,
        )

        st.markdown("**Financial context**")
        f1, f2, f3 = st.columns(3)
        f1.metric("Unit Cost", format_gbp(row["Unit_Cost"]))
        f2.metric("Unit Price", format_gbp(row["Unit_Price"]))
        f3.metric("Gross Margin %", f"{row['Gross_Margin_Pct']*100:.1f}%")

    with tab_priority:
        if pd.isna(row["Priority_Score"]):
            st.markdown(
                priority_dot_label_html(label, LABEL_COLORS[label])
                + " &nbsp;&nbsp; This SKU-Store is within target — no DIO intervention required, so it was never scored by the Priority module.",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"**Priority Score: {row['Priority_Score']:.2f} / 5.0** &nbsp;&nbsp; "
                + priority_dot_label_html(label, LABEL_COLORS[label]),
                unsafe_allow_html=True,
            )
            st.markdown("<br>", unsafe_allow_html=True)
            p1, p2, p3, p4 = st.columns(4)
            p1.metric("Urgency Score", f"{row['Urgency_Score']:.0f} / 5")
            p2.metric("DIO Severity Score", f"{row['DIO_Severity_Score']:.0f} / 5")
            p3.metric("Margin Score", f"{row['Margin_Score']:.0f} / 5")
            p4.metric("Excess Value Score", f"{row['Excess_Value_Score']:.0f} / 5")

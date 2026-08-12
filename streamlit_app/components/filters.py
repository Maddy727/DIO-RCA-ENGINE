"""
filters.py

Consistent filter panel. Only exposes filters that exist as real fields in
the joined data — no fabricated filter dimensions.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st


def render_filter_panel(df: pd.DataFrame, key_prefix: str,
                         fields: list[str] | None = None) -> pd.DataFrame:
    """
    Renders a multiselect filter for each requested field (defaults to the
    standard set below, minus any not present in df) and returns the
    filtered dataframe.
    """
    default_fields = [
        "Region", "Store_Name", "Store_Format", "Category", "SKU_ID",
        "Root_Cause", "Problem_Area", "Action_Owner", "Priority_Label",
        "S21_Is_Perishable",
    ]
    fields = [f for f in (fields or default_fields) if f in df.columns]
    if not fields:
        return df

    with st.expander("Filters", expanded=False):
        cols = st.columns(min(4, len(fields)))
        selections = {}
        for i, field in enumerate(fields):
            with cols[i % len(cols)]:
                options = sorted(df[field].dropna().unique().tolist())
                label = field.replace("_", " ")
                if field == "S21_Is_Perishable":
                    label = "Perishable"
                    options = ["Yes", "No"]
                selections[field] = st.multiselect(label, options, key=f"{key_prefix}_{field}")

    filtered = df.copy()
    for field, selected in selections.items():
        if not selected:
            continue
        if field == "S21_Is_Perishable":
            wanted = [1 if s == "Yes" else 0 for s in selected]
            filtered = filtered[filtered[field].isin(wanted)]
        else:
            filtered = filtered[filtered[field].isin(selected)]
    return filtered

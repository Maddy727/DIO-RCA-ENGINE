"""
tables.py

Reusable interactive table rendering (thin wrapper over st.dataframe with
consistent formatting), plus a click-to-select helper used by the
drill-down component.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st


def render_table(df: pd.DataFrame, gbp_cols: list[str] | None = None,
                  day_cols: list[str] | None = None, key: str | None = None,
                  selectable: bool = False):
    """
    Renders a dataframe with £ / day formatting on specified columns.
    If selectable=True, returns the selected row (or None) via
    st.dataframe's built-in row-selection — used for drill-down click-through.
    """
    display_df = df.copy()
    for c in gbp_cols or []:
        if c in display_df.columns:
            display_df[c] = display_df[c].apply(lambda v: f"£{v:,.0f}" if pd.notna(v) else "")
    for c in day_cols or []:
        if c in display_df.columns:
            display_df[c] = display_df[c].apply(lambda v: f"{v:.1f}d" if pd.notna(v) else "")

    if selectable:
        event = st.dataframe(
            display_df, width='stretch', hide_index=True, key=key,
            on_select="rerun", selection_mode="single-row",
        )
        if event.selection and event.selection.get("rows"):
            return df.iloc[event.selection["rows"][0]]
        return None

    st.dataframe(display_df, width='stretch', hide_index=True, key=key)
    return None

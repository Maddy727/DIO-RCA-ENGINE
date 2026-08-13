"""
tables.py

Reusable interactive table rendering.

Real bug fixed here (found and confirmed, not guessed): £ columns were
being converted to formatted STRINGS ("£1,000") before display so they
*looked* right, but Streamlit's column-header sort then sorted those as
text — "£10,000" sorts before "£2,000" alphabetically. Fixed by keeping
columns numeric and using Streamlit's column_config (NumberColumn) for
DISPLAY formatting instead — sort then operates on the real numbers.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from .styling import empty_state_message

# Client-friendly display labels for technical/internal field names.
# Presentation-only — never renames the underlying data field.
FRIENDLY_LABELS = {
    "SKU_Store_Count": "Count of SKUs",
    "SKU_ID": "SKU",
    "SKU_Name": "Product",
    "Store_ID": "Store ID",
    "Store_Name": "Store",
    "Store_Format": "Format",
    "DIO_Variance": "DIO Variance",
    "DIO_Target": "DIO Target",
    "Inventory_Value": "Inventory Value",
    "Excess_Value": "Excess Value",
    "Excess_Units": "Excess Units",
    "Priority_Score": "Priority Score",
    "Priority_Label": "Priority",
    "Root_Cause": "Root Cause",
    "Root_Cause_Summary": "Root Cause",
    "Problem_Area": "Problem Area",
    "Action_Owner": "Action Owner",
    "Review_Owner": "Review Owner",
    "Corrective_Action": "Corrective Action",
    "Store_Action_Recommendation": "Store Action",
    "Current_Stock_Units": "Current Stock",
    "Target_Stock_Units": "Target Stock",
    "Rank": "Rank",
}


def render_table(df: pd.DataFrame, gbp_cols: list[str] | None = None,
                  day_cols: list[str] | None = None, key: str | None = None,
                  selectable: bool = False, rename: bool = True,
                  height: int | None = None):
    """
    Renders a dataframe with £ / day formatting applied via column_config
    (keeps underlying values numeric, so header-click sorting is correct
    numerically, not alphabetically) and client-friendly column headers.

    If selectable=True, returns the selected row (from the ORIGINAL,
    unrenamed df) via st.dataframe's built-in row-selection.

    If df is empty, shows the standard empty-state message instead of a
    blank/default Streamlit table.
    """
    if df is None or df.empty:
        empty_state_message()
        return None

    display_df = df.copy()
    column_config = {}
    for c in gbp_cols or []:
        if c in display_df.columns:
            column_config[c] = st.column_config.NumberColumn(
                FRIENDLY_LABELS.get(c, c) if rename else c, format="£%,.0f",
            )
    for c in day_cols or []:
        if c in display_df.columns:
            column_config[c] = st.column_config.NumberColumn(
                FRIENDLY_LABELS.get(c, c) if rename else c, format="%.1fd",
            )
    if rename:
        for col in display_df.columns:
            if col in FRIENDLY_LABELS and col not in column_config:
                column_config[col] = st.column_config.Column(FRIENDLY_LABELS[col])

    kwargs = dict(width="stretch", hide_index=True, key=key, column_config=column_config)
    if height:
        kwargs["height"] = height

    if selectable:
        event = st.dataframe(display_df, on_select="rerun", selection_mode="single-row", **kwargs)
        if event.selection and event.selection.get("rows"):
            return df.iloc[event.selection["rows"][0]]
        return None

    st.dataframe(display_df, **kwargs)
    return None


def add_rank_column(df: pd.DataFrame, sort_col: str, ascending: bool = False) -> pd.DataFrame:
    """
    Adds an explicit Rank column (1 = best per sort_col direction), placed
    as the first column. Rank 1 = highest sort_col value by default (e.g.
    highest DIO), matching "Rank 1 = highest DIO" requirement.
    """
    out = df.sort_values(sort_col, ascending=ascending).reset_index(drop=True)
    out.insert(0, "Rank", range(1, len(out) + 1))
    return out

"""
aggregations.py

Presentation-layer aggregation helpers shared across pages. None of these
create new business logic — they group/summarize the engine's own output
fields (Root_Cause, Problem_Area, Action_Owner, etc.).
"""
from __future__ import annotations

import pandas as pd


def summarize_root_causes(rca_long: pd.DataFrame) -> pd.DataFrame:
    """
    Per your confirmed decision: one summary row per SKU-Store with
    "Root_Cause + N more" (e.g. "Excess Supply + 2 more"). This is a
    PRESENTATION-ONLY summary — the underlying rca_long dataframe (passed
    in, untouched) still has every root cause as a separate row; nothing
    is deduplicated or overwritten there.
    """
    def _summarize(g: pd.DataFrame) -> str:
        causes = g["Root_Cause"].tolist()
        if len(causes) == 1:
            return causes[0]
        return f"{causes[0]} + {len(causes) - 1} more"

    summary = (
        rca_long.groupby(["SKU_ID", "Store_ID"])
        .apply(_summarize, include_groups=False)
        .reset_index(name="Root_Cause_Summary")
    )
    counts = (
        rca_long.groupby(["SKU_ID", "Store_ID"])
        .size()
        .reset_index(name="Root_Cause_Count")
    )
    return summary.merge(counts, on=["SKU_ID", "Store_ID"])


def problem_area_split(rca_long: pd.DataFrame) -> pd.DataFrame:
    """Count of fired root causes by Problem Area (Demand/Supply/Network/Others)."""
    return (
        rca_long.groupby("Problem_Area")
        .size()
        .reset_index(name="Count")
        .sort_values("Count", ascending=False)
    )


def owner_accountability(corrective_action_long: pd.DataFrame, financial_by_sku_store: pd.DataFrame) -> pd.DataFrame:
    """
    Excess Value + affected SKU-Store count by Action Owner. Joins the
    long-format corrective action output (one row per root cause) to
    financial data (one row per SKU-Store) on SKU_ID+Store_ID, then
    de-duplicates SKU-Stores per owner before summing Excess Value (so a
    SKU-Store with 2 root causes both owned by the same person doesn't
    double-count its Excess Value for that owner).
    """
    merged = corrective_action_long.merge(
        financial_by_sku_store[["SKU_ID", "Store_ID", "Excess_Value"]],
        on=["SKU_ID", "Store_ID"], how="left",
    )
    dedup = merged.drop_duplicates(subset=["SKU_ID", "Store_ID", "Action_Owner"])
    return (
        dedup.groupby("Action_Owner")
        .agg(Excess_Value=("Excess_Value", "sum"), SKU_Store_Count=("SKU_ID", "count"))
        .reset_index()
        .sort_values("Excess_Value", ascending=False)
    )


def category_x_problem_area(rca_long: pd.DataFrame, master: pd.DataFrame) -> pd.DataFrame:
    """Pivot: Category (rows) x Problem Area (columns), cell = count of fired root causes."""
    merged = rca_long.merge(master[["SKU_ID", "Store_ID", "Category"]], on=["SKU_ID", "Store_ID"], how="left")
    pivot = pd.pivot_table(
        merged, index="Category", columns="Problem_Area", values="Root_Cause",
        aggfunc="count", fill_value=0,
    )
    return pivot


def dashboard_view_filter(corrective_action_long: pd.DataFrame, view: str) -> pd.DataFrame:
    """
    Filters the corrective action output to rows whose Dashboard_View
    contains the given persona scope (e.g. 'Store', 'Regional', 'Central').
    Uses the EXISTING Dashboard_View field from the approved mapping file
    — does not invent a new persona-routing rule.
    """
    return corrective_action_long[
        corrective_action_long["Dashboard_View"].str.contains(view, case=False, na=False)
    ]

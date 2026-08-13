"""
dio_aggregation.py

Presentation-layer aggregation methodology. This module defines HOW numbers
that appear on every KPI card and ranking table are rolled up — it does not
create any new business rule, RCA logic, or engine output. Every input
field used here is already validated/approved (S01_Weeks_Cover,
S01_Weeks_Cover_Target, Current_Stock_Units, Unit_Cost, Excess_Units).

=====================================================================
DIO METHODOLOGY (confirmed: value-weighted, not a naive average)
=====================================================================
Per SKU-Store:
    DIO_days        = S01_Weeks_Cover * 7                (approved formula, unchanged)
    DIO_Target_days  = S01_Weeks_Cover_Target * 7          (approved formula, unchanged)
    Inventory_Value  = Current_Stock_Units * Unit_Cost      (approved formula, unchanged)
    Daily_Units_Sold  = Current_Stock_Units / DIO_days       (back-derived from the same
                        Weeks-Cover-implied sales rate used to build Current_Stock_Units in
                        Financial_Impact_Data.xlsx; undefined/zero when DIO_days == 0)
    Daily_COGS         = Daily_Units_Sold * Unit_Cost

Aggregate DIO (store / category / region / enterprise level):
    Aggregate_DIO = SUM(Inventory_Value) / SUM(Daily_COGS)

This is the standard finance definition of aggregate Days Inventory
Outstanding (total inventory $ divided by daily cost of goods sold), NOT a
simple average of individual SKU DIO values. A naive average would let a
handful of low-value, slow-moving SKUs skew the headline number just as
much as a small number of high-value ones — the value-weighted approach
means the KPI reflects where the £ actually sits.

Rows where DIO_days == 0 (i.e. zero Weeks Cover — the one "Stock Expired,
zero stock on hand" scenario in the sample) are excluded from the Daily_COGS
sum (they contribute Inventory_Value = 0 and Daily_COGS = 0, so they don't
distort the ratio either way).

Aggregate DIO_Target uses the SAME weighting basis (SUM(Inventory_Value) /
SUM(Daily_COGS at target)) is NOT used for the target line — instead,
DIO_Target is shown as the SAME value-weighted average, weighted by each
row's Inventory_Value, for direct visual comparability against Aggregate_DIO
on the same chart. This is documented here as a presentation choice: the
Target itself doesn't have its own "Daily COGS at target" concept, so a
value-weighted average (not a Value/COGS ratio) is used for it specifically.
"""
from __future__ import annotations

import pandas as pd


def add_dio_fields(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds per-row presentation fields to a wide (one-row-per-SKU-Store)
    dataframe: DIO, DIO_Target, DIO_Variance, Inventory_Value,
    Daily_Units_Sold, Daily_COGS. Does not mutate the input; returns a new
    dataframe.

    Note: DIO_Variance here is the simple per-row DIO - DIO_Target (no
    weighting needed at row level — value-weighting only matters when
    AGGREGATING across multiple rows, which rollup() below handles
    separately for grouped views).
    """
    out = df.copy()
    out["DIO"] = out["S01_Weeks_Cover"] * 7
    out["DIO_Target"] = out["S01_Weeks_Cover_Target"] * 7
    out["DIO_Variance"] = out["DIO"] - out["DIO_Target"]
    out["Inventory_Value"] = out["Current_Stock_Units"] * out["Unit_Cost"]
    out["Daily_Units_Sold"] = out.apply(
        lambda r: (r["Current_Stock_Units"] / r["DIO"]) if r["DIO"] and r["DIO"] > 0 else 0.0,
        axis=1,
    )
    out["Daily_COGS"] = out["Daily_Units_Sold"] * out["Unit_Cost"]
    return out


def weighted_dio(df: pd.DataFrame) -> float:
    """Value-weighted aggregate DIO (days) for the given slice of rows."""
    total_value = df["Inventory_Value"].sum()
    total_daily_cogs = df["Daily_COGS"].sum()
    if total_daily_cogs == 0:
        return 0.0
    return total_value / total_daily_cogs


def weighted_dio_target(df: pd.DataFrame) -> float:
    """
    Value-weighted average DIO_Target (days), weighted by each row's
    Inventory_Value, so it's directly comparable on the same axis as
    weighted_dio() above. See module docstring for why this differs
    methodologically from weighted_dio() itself.
    """
    total_value = df["Inventory_Value"].sum()
    if total_value == 0:
        return 0.0
    return (df["DIO_Target"] * df["Inventory_Value"]).sum() / total_value


def rollup(df: pd.DataFrame, group_by: str | list[str] | None = None) -> pd.DataFrame:
    """
    Rolls up a (DIO-field-enriched) wide dataframe to the given group_by
    level (e.g. 'Store_ID', 'Category', ['Region']), or to a single overall
    row if group_by is None.

    Returns columns: [group_by...], DIO, DIO_Target, DIO_Variance,
    Inventory_Value, Excess_Value, SKU_Store_Count.
    """
    def _agg(g: pd.DataFrame) -> pd.Series:
        return pd.Series({
            "DIO": round(weighted_dio(g), 1),
            "DIO_Target": round(weighted_dio_target(g), 1),
            "DIO_Variance": round(weighted_dio(g) - weighted_dio_target(g), 1),
            "Inventory_Value": g["Inventory_Value"].sum(),
            "Excess_Value": g["Excess_Value"].sum(),
            "SKU_Store_Count": len(g),
        })

    if group_by is None:
        return _agg(df).to_frame().T

    result = df.groupby(group_by, dropna=False).apply(_agg, include_groups=False).reset_index()
    return result

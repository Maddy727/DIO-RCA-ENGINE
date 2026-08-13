"""
priority_labels.py

Normalizes Priority_Score against its DEFINED maximum (not the observed
max in any given dataset slice) and applies the confirmed 5-label banding.

Defined max Priority Score, from config/priority_logic.yaml's approved
sub-score tables (Urgency max=5, Margin max=5, Excess Value max=5, DIO
Severity max=5):
    0.7*5 + 0.1*5 + 0.1*5 + 0.1*5 = 5.0

Confirmed cutoffs (>= is used at each boundary, consistent with how the
approved Priority_Logic.xlsx tables use inclusive "<=" boundaries):
    >= 80% -> Emergency
    >= 60% -> Urgent
    >= 40% -> High
    >= 20% -> Medium
    >= 0%  -> Low
"""
from __future__ import annotations

import pandas as pd

MAX_PRIORITY_SCORE = 5.0

LABEL_COLORS = {
    "Emergency": "#C81E3A",
    "Urgent": "#D97B0A",
    "High": "#E0A800",
    "Medium": "#0B5AA8",
    "Low": "#6C7688",
    "Not Scored": "#C4CAD4",
}

LABEL_ORDER = ["Emergency", "Urgent", "High", "Medium", "Low"]


def normalize_priority_pct(priority_score: float) -> float:
    if priority_score is None or pd.isna(priority_score):
        return float("nan")
    return (priority_score / MAX_PRIORITY_SCORE) * 100.0


def priority_label(priority_score: float) -> str:
    """
    Returns one of the 5 approved labels, or "Not Scored" for SKU-Stores
    the Priority module never scored (healthy/non-eligible — DIO within
    target, no RCA action). "Not Scored" is NOT one of the 5 approved
    priority bands and must never be conflated with "Low" — a genuinely
    low-urgency-but-eligible SKU is a different thing from a healthy SKU
    that was never scored at all. (Bug found and fixed: NaN comparisons
    like `NaN >= 80` are always False in Python, so unscored rows were
    silently falling through to "Low" before this fix.)
    """
    if priority_score is None or pd.isna(priority_score):
        return "Not Scored"
    pct = normalize_priority_pct(priority_score)
    if pct >= 80:
        return "Emergency"
    if pct >= 60:
        return "Urgent"
    if pct >= 40:
        return "High"
    if pct >= 20:
        return "Medium"
    return "Low"


def add_priority_label(df: pd.DataFrame, score_col: str = "Priority_Score") -> pd.DataFrame:
    """Adds Priority_Pct and Priority_Label columns. Does not mutate input."""
    out = df.copy()
    out["Priority_Pct"] = out[score_col].apply(normalize_priority_pct)
    out["Priority_Label"] = out[score_col].apply(priority_label)
    return out


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from utils.data_loader import load_all

    data = load_all()
    labeled = add_priority_label(data["wide"])
    print(labeled["Priority_Label"].value_counts().reindex(LABEL_ORDER, fill_value=0))

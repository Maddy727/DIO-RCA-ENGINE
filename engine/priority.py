"""
priority.py — Layer 7

Computes the four Priority_Logic.xlsx sub-scores and the final weighted
Priority Score, for the "DIO intervention population" only (rows where the
RCA engine produced at least one real root cause, i.e. NOT "No Action
Required" — Gap-4-consistent: perishable expiry findings count as eligible
even when the Weeks Cover gate is closed).

Sub-score population, per your confirmed decisions:
  - Urgency Score:      global, table lookup, no percentile
  - DIO Severity Score: global, table lookup, no percentile
  - Margin Score:       percentile WITHIN Store_ID, eligible population only
  - Excess Value Score: percentile WITHIN Store_ID, eligible population only
  - Small-population fallback: stores with < 4 eligible rows get a fixed
    Margin_Score = Excess_Value_Score = 3, percentile fields left None.
    No network-wide fallback, no raw-rank substitute (per your instruction).

Two implementation notes on undefined table inputs (flagged here, not
silently assumed to be "business logic" — these are gaps in the table's
domain, not values I invented):
  - Urgency: if BOTH S22_Shelf_Life_Remaining_Days and S09_Days_To_Season_End
    are unavailable/sentinel (-1) for a row (i.e. not perishable and not
    seasonal), there is no MIN() to score against any band. Treated as
    falling in the lowest urgency band (">30 days", score=1), since no
    imminent expiry/season-end deadline exists for that row.
  - DIO Severity: the table only defines bands for ratio >= 1.5x Target.
    A row that is eligible via the perishable bypass but has a DIO ratio
    below 1.5x (e.g. near-zero Weeks Cover on an expired item) doesn't hit
    any band. Treated as DIO Severity Score = 0 (no defined severity).
Both are flagged in the validation summary — please confirm or override.
"""
from __future__ import annotations

import os
from bisect import bisect_right
from dataclasses import dataclass

import yaml

CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "config")


@dataclass
class PriorityResult:
    sku_id: str
    store_id: str
    urgency_score: float
    dio_severity_score: float
    margin_score: float
    excess_value_score: float
    margin_percentile_within_store: float | None
    excess_value_percentile_within_store: float | None
    store_eligible_population_size: int
    priority_score: float


def _f(row, key):
    v = row.get(key)
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return v


def load_priority_config(config_dir: str = CONFIG_DIR) -> dict:
    with open(os.path.join(config_dir, "priority_logic.yaml")) as f:
        return yaml.safe_load(f)


class PriorityEngine:
    def __init__(self, config_dir: str = CONFIG_DIR):
        self.config = load_priority_config(config_dir)
        self.small_pop_threshold = self.config["small_population_fallback"]["threshold_eligible_rows"]

    # ------------------------------------------------------------------
    # Global sub-scores
    # ------------------------------------------------------------------
    def urgency_score(self, row) -> float:
        slr = _f(row, "S22_Shelf_Life_Remaining_Days")
        dtse = _f(row, "S09_Days_To_Season_End")
        candidates = [v for v in (slr, dtse) if v is not None and v != -1]
        if not candidates:
            return 1.0  # lowest band — see module docstring note
        min_val = min(candidates)
        for band in self.config["urgency_score_table"]:
            op = band["Operator"]
            threshold = band["Threshold"]
            if op == "<=" and min_val <= threshold:
                return float(band["Urgency Score"])
            if op == ">" and min_val > threshold:
                return float(band["Urgency Score"])
        return 1.0

    def dio_severity_score(self, row) -> float:
        wc = _f(row, "S01_Weeks_Cover")
        wct = _f(row, "S01_Weeks_Cover_Target")
        if wc is None or wct is None or wct == 0:
            return 0.0
        ratio = wc / wct  # DIO/DIO_Target = (WC*7)/(WCT*7) = WC/WCT
        # Table is ordered highest threshold first (5x, 4x, 3x, 2x, 1.5x)
        for band in self.config["dio_severity_score_table"]:
            factor_text = band["Factor"]
            threshold = float(factor_text.split(">=")[1].split("x")[0].strip())
            if ratio >= threshold:
                return float(band["DIO Severity Score"])
        return 0.0  # below 1.5x — see module docstring note

    # ------------------------------------------------------------------
    # Within-store percentile sub-scores
    # ------------------------------------------------------------------
    @staticmethod
    def _percentile_rank(value: float, sorted_values: list[float]) -> float:
        """Percent of the population <= value (0-100), 'less-than-or-equal' convention."""
        n = len(sorted_values)
        if n == 0:
            return 0.0
        idx = bisect_right(sorted_values, value)
        return (idx / n) * 100.0

    def _score_from_percentile(self, pct: float, table: list[dict], score_field: str,
                                direction: str) -> float:
        """
        direction='low_is_high': lowest percentile -> highest score (Margin)
        direction='high_is_high': highest percentile -> highest score (Excess Value)
        """
        if direction == "low_is_high":
            if pct <= 20:
                return 5.0
            if pct <= 40:
                return 4.0
            if pct <= 60:
                return 3.0
            if pct <= 80:
                return 2.0
            return 1.0
        else:  # high_is_high
            if pct >= 80:
                return 5.0
            if pct >= 60:
                return 4.0
            if pct >= 40:
                return 3.0
            if pct >= 20:
                return 2.0
            return 1.0

    # ------------------------------------------------------------------
    def compute_for_store(self, eligible_rows_with_financials: list[dict]) -> dict[tuple[str, str], dict]:
        """
        eligible_rows_with_financials: list of dicts, each with at least
        'SKU_ID', 'Store_ID', 'Gross_Margin_Pct', 'Excess_Value' — ALL
        belonging to the SAME store, ALL already filtered to the eligible
        (DIO intervention) population.

        Returns {(sku_id, store_id): {margin_score, excess_value_score,
                                       margin_pct, excess_value_pct}}
        """
        n = len(eligible_rows_with_financials)
        out = {}

        if n < self.small_pop_threshold:
            for r in eligible_rows_with_financials:
                out[(r["SKU_ID"], r["Store_ID"])] = {
                    "margin_score": 3.0,
                    "excess_value_score": 3.0,
                    "margin_pct": None,
                    "excess_value_pct": None,
                }
            return out

        margins_sorted = sorted(r["Gross_Margin_Pct"] for r in eligible_rows_with_financials)
        excess_values_sorted = sorted(r["Excess_Value"] for r in eligible_rows_with_financials)

        for r in eligible_rows_with_financials:
            margin_pct = self._percentile_rank(r["Gross_Margin_Pct"], margins_sorted)
            excess_value_pct = self._percentile_rank(r["Excess_Value"], excess_values_sorted)
            margin_score = self._score_from_percentile(margin_pct, None, None, "low_is_high")
            excess_value_score = self._score_from_percentile(excess_value_pct, None, None, "high_is_high")
            out[(r["SKU_ID"], r["Store_ID"])] = {
                "margin_score": margin_score,
                "excess_value_score": excess_value_score,
                "margin_pct": margin_pct,
                "excess_value_pct": excess_value_pct,
            }
        return out

    # ------------------------------------------------------------------
    def compute_all(self, eligible_rows: list, financial_lookup: dict) -> list[PriorityResult]:
        """
        eligible_rows: list of SkuStoreRow objects, ALREADY FILTERED to the
        DIO intervention population (see priority_eligibility.py / caller).
        financial_lookup: {(SKU_ID, Store_ID): Financial_Impact_Data record}
        """
        # Group by store for percentile calc
        by_store: dict[str, list[dict]] = {}
        for row in eligible_rows:
            fin = financial_lookup.get((row["SKU_ID"], row["Store_ID"]))
            if fin is None:
                continue  # no financial data — cannot score Margin/Excess Value for this row
            by_store.setdefault(row["Store_ID"], []).append({
                "SKU_ID": row["SKU_ID"], "Store_ID": row["Store_ID"],
                "Gross_Margin_Pct": fin["Gross_Margin_Pct"], "Excess_Value": fin["Excess_Value"],
            })

        store_scores: dict[tuple[str, str], dict] = {}
        store_sizes: dict[str, int] = {}
        for store_id, records in by_store.items():
            store_sizes[store_id] = len(records)
            store_scores.update(self.compute_for_store(records))

        results = []
        for row in eligible_rows:
            key = (row["SKU_ID"], row["Store_ID"])
            scores = store_scores.get(key)
            if scores is None:
                continue  # no financial data for this SKU-Store
            urgency = self.urgency_score(row)
            dio_sev = self.dio_severity_score(row)
            priority = 0.7 * urgency + 0.1 * scores["margin_score"] + 0.1 * scores["excess_value_score"] + 0.1 * dio_sev
            results.append(PriorityResult(
                sku_id=row["SKU_ID"], store_id=row["Store_ID"],
                urgency_score=urgency, dio_severity_score=dio_sev,
                margin_score=scores["margin_score"], excess_value_score=scores["excess_value_score"],
                margin_percentile_within_store=scores["margin_pct"],
                excess_value_percentile_within_store=scores["excess_value_pct"],
                store_eligible_population_size=store_sizes[row["Store_ID"]],
                priority_score=round(priority, 3),
            ))
        return results


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from data_mapping import load_sku_store_data, load_financial_impact_data
    from rca_engine import RcaEngine

    rows = load_sku_store_data("data/sample/Sample_RCA_Data.xlsx")
    fin = load_financial_impact_data("data/sample/Financial_Impact_Data.xlsx")
    rca = RcaEngine()

    eligible = []
    for row in rows:
        findings = rca.evaluate(row)
        if any(f.root_cause != "No Action Required" for f in findings):
            eligible.append(row)

    print(f"Eligible (DIO intervention population): {len(eligible)} / {len(rows)}")

    engine = PriorityEngine()
    results = engine.compute_all(eligible, fin)
    results.sort(key=lambda r: -r.priority_score)
    for r in results[:10]:
        print(f"{r.sku_id:16s} store={r.store_id:8s} priority={r.priority_score:.3f} "
              f"urgency={r.urgency_score} margin={r.margin_score} excess_val={r.excess_value_score} "
              f"dio_sev={r.dio_severity_score} pop={r.store_eligible_population_size}")

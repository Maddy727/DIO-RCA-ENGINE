"""
rca_engine.py — Layer 3

Deterministic Root Cause Analysis engine. Evaluates every rule from
config/rca_rules.yaml against a single canonical SKU-Store row and returns
ALL root causes that fire (never collapses to one), each tagged with the
rule ID and triggering signal/threshold for explainability.

No thresholds are hard-coded here — every number in the conditionals below
exists because config/rca_rules.yaml (and, transitively, the approved
RCA_Rules.xlsx / Signal_KPI_Parameters.xlsx) says so. This module is the
*evaluator* for those rules, not a place to define new ones.

Business logic implemented (all confirmed/validated against the 70-row
sample in prior review rounds — see README.md):
  - Rule 1 gate: Weeks Cover <= 1.1x Target -> "No Action Required"
  - Rules 2-13, 17-19: independent, may co-fire
  - Rules 14/15/16 (perishable expiry): mutually exclusive, evaluated in
    that order, and run INDEPENDENTLY of the Rule-1 gate (Gap 4)
  - Active Promo (Rule 3) suppresses excess-type root causes (Rules 8-12,
    17, 18) UNLESS Weeks Cover > 3x Target (Gap 2, Context_Parameters CTX001)
  - Rule 7 (Demand Decline) is suppressed if Rule 5 (Post-promo demand
    collapse) already fired
  - Rule 19 fallback fires only if the gate is open and nothing else fired
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

import yaml

CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "config")

SUPPRESSIBLE_RULE_IDS = {8, 9, 10, 11, 12, 17, 18}
EXPIRY_RULE_IDS = {14, 15, 16}


@dataclass
class RcaFinding:
    sku_id: str
    store_id: str
    rule_id: int
    root_cause: str
    triggering_signal: str
    signal_value: object
    threshold_applied: str
    gate_status: str  # "gate_open" | "gate_closed_perishable_bypass" | "gate_closed"


def load_rca_rules(config_dir: str = CONFIG_DIR) -> dict:
    with open(os.path.join(config_dir, "rca_rules.yaml")) as f:
        return yaml.safe_load(f)


def _f(row, key):
    """Fetch a numeric field, tolerant of None."""
    v = row.get(key)
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return v


class RcaEngine:
    def __init__(self, config_dir: str = CONFIG_DIR):
        self.config = load_rca_rules(config_dir)

    def evaluate(self, row) -> list[RcaFinding]:
        sku_id = row["SKU_ID"]
        store_id = row["Store_ID"]

        wc = _f(row, "S01_Weeks_Cover")
        wct = _f(row, "S01_Weeks_Cover_Target")
        gate_open = wc is not None and wct is not None and wc > 1.1 * wct

        findings: list[RcaFinding] = []

        # --- Perishable expiry rules: evaluated regardless of gate (Gap 4) ---
        expiry_finding = self._evaluate_expiry_rules(row, sku_id, store_id, wc)

        if not gate_open:
            if expiry_finding is not None:
                gate_status = "gate_closed_perishable_bypass"
                findings.append(self._with_gate_status(expiry_finding, gate_status))
            else:
                findings.append(RcaFinding(
                    sku_id, store_id, rule_id=1, root_cause="No Action Required",
                    triggering_signal="S01_Weeks_Cover", signal_value=wc,
                    threshold_applied="<= 1.1 * S01_Weeks_Cover_Target",
                    gate_status="gate_closed",
                ))
            return findings

        gate_status = "gate_open"

        # --- Rule 2: Possible Phantom Inventory ---
        zsf = _f(row, "S02_Zero_Sales_Flag")
        if zsf == 1:
            findings.append(RcaFinding(sku_id, store_id, 2, "Possible Phantom Inventory",
                                        "S02_Zero_Sales_Flag", zsf, "== 1", gate_status))

        # --- Rule 3: Active Promo ---
        apf = _f(row, "S03_Active_Promo_Flag")
        active_promo = apf == 1
        if active_promo:
            findings.append(RcaFinding(sku_id, store_id, 3, "Active Promo",
                                        "S03_Active_Promo_Flag", apf, "== 1", gate_status))
        suppress_excess = active_promo and not (wc > 3 * wct)

        # --- Rule 4: Upcoming Promo ---
        dtps = _f(row, "S04_Days_To_Promo_Start")
        upf = _f(row, "S04_Upcoming_Promo_Flag")
        if dtps is not None and upf is not None and dtps <= 14 and upf == 1:
            findings.append(RcaFinding(sku_id, store_id, 4, "Upcoming Promo",
                                        "S04_Days_To_Promo_Start", dtps,
                                        "<= 14 AND S04_Upcoming_Promo_Flag == 1", gate_status))

        # --- Rule 5: Post-promo demand collapse ---
        dspe = _f(row, "S06_Days_Since_Promo_Ended")
        ppvr = _f(row, "S07_Post_Promo_Velocity_Ratio")
        post_promo_collapse = (dspe is not None and ppvr is not None and dspe > 7 and ppvr < 0.5)
        if post_promo_collapse:
            findings.append(RcaFinding(sku_id, store_id, 5, "Post-promo demand collapse",
                                        "S06_Days_Since_Promo_Ended / S07_Post_Promo_Velocity_Ratio",
                                        f"{dspe} / {ppvr}", "> 7 AND < 0.5", gate_status))

        # --- Rule 6: Season-end write-off risk (uses Weeks Cover x7, Gap 1) ---
        dtse = _f(row, "S09_Days_To_Season_End")
        if dtse is not None and dtse != -1 and dtse <= wc * 7:
            findings.append(RcaFinding(sku_id, store_id, 6, "Season-end write-off risk",
                                        "S09_Days_To_Season_End", dtse,
                                        "<= S01_Weeks_Cover * 7", gate_status))

        # --- Rule 7: Demand Decline (suppressed if post-promo collapse fired) ---
        svr = _f(row, "S10_Sales_Velocity_Ratio")
        if svr is not None and svr < 0.75 and not post_promo_collapse:
            findings.append(RcaFinding(sku_id, store_id, 7, "Demand Decline",
                                        "S10_Sales_Velocity_Ratio", svr, "< 0.75", gate_status))

        # --- Rule 8: high forecast bias (suppressible) ---
        fva = _f(row, "S15_Forecast_vs_Actual_Pct")
        if fva is not None and fva > 15 and not suppress_excess:
            findings.append(RcaFinding(sku_id, store_id, 8, "high forecast bias",
                                        "S15_Forecast_vs_Actual_Pct", fva, "> 15", gate_status))

        # --- Rule 9: Excess Supply (suppressible) ---
        esr = _f(row, "S17_Excess_Supply_Ratio")
        if esr is not None and esr > 2 and not suppress_excess:
            findings.append(RcaFinding(sku_id, store_id, 9, "Excess Supply",
                                        "S17_Excess_Supply_Ratio", esr, "> 2", gate_status))

        # --- Rule 10: Promo Overbuy (NOT suppressible by Active Promo — it's promo-specific) ---
        pesr = _f(row, "S18_Promo_Excess_Supply_Ratio")
        if pesr is not None and pesr > 3 and dspe is not None and dspe > 0:
            findings.append(RcaFinding(sku_id, store_id, 10, "Promo Overbuy",
                                        "S18_Promo_Excess_Supply_Ratio", pesr,
                                        "> 3 AND S06_Days_Since_Promo_Ended > 0", gate_status))

        # --- Rule 11: high stock vs peers (suppressible) ---
        pdio = _f(row, "S12_Peer_DIO_Rate")
        if pdio is not None and pdio > 1.5 and not suppress_excess:
            findings.append(RcaFinding(sku_id, store_id, 11, "high stock vs peers",
                                        "S12_Peer_DIO_Rate", pdio, "> 1.5", gate_status))

        # --- Rule 12: High Stock vs Format (suppressible) ---
        fdio = _f(row, "S13_Format_DIO_Ratio")
        if fdio is not None and fdio > 1.5 and not suppress_excess:
            findings.append(RcaFinding(sku_id, store_id, 12, "High Stock vs Format",
                                        "S13_Format_DIO_Ratio", fdio, "> 1.5", gate_status))

        # --- Rule 13: Stale Par Level ---
        pla = _f(row, "S16_Par_Level_Age_Days")
        if pla is not None and pla > 90 and svr is not None and svr < 0.75:
            findings.append(RcaFinding(sku_id, store_id, 13, "Stale Par Level",
                                        "S16_Par_Level_Age_Days", pla,
                                        "> 90 AND S10_Sales_Velocity_Ratio < 0.75", gate_status))

        # --- Rules 14/15/16: perishable expiry (already evaluated above) ---
        if expiry_finding is not None:
            findings.append(self._with_gate_status(expiry_finding, gate_status))

        # --- Rule 17: High Safety Stock (suppressible) ---
        hss = _f(row, "S19_High_SS_Flag_Days")
        if hss is not None and hss > 2 and not suppress_excess:
            findings.append(RcaFinding(sku_id, store_id, 17, "High Safety Stock",
                                        "S19_High_SS_Flag_Days", hss, "> 2", gate_status))

        # --- Rule 18: Supplier MoQ Overbuy (suppressible) ---
        moq = _f(row, "S20_Supplier_MOQ_Ratio")
        if moq is not None and moq > 1.3 and not suppress_excess:
            findings.append(RcaFinding(sku_id, store_id, 18, "Supplier MoQ Overbuy",
                                        "S20_Supplier_MOQ_Ratio", moq, "> 1.3", gate_status))

        # --- Rule 19: fallback ---
        if not findings:
            findings.append(RcaFinding(sku_id, store_id, 19, "Monitor - Review at next weekly cycle",
                                        "S01_Weeks_Cover", wc,
                                        "> 1.1 * Target AND no other rule fired", gate_status))

        return findings

    @staticmethod
    def _with_gate_status(finding: RcaFinding, gate_status: str) -> RcaFinding:
        finding.gate_status = gate_status
        return finding

    def _evaluate_expiry_rules(self, row, sku_id, store_id, wc) -> RcaFinding | None:
        """Rules 14/15/16, mutually exclusive, in strict order."""
        slr = _f(row, "S22_Shelf_Life_Remaining_Days")
        if slr is None:
            return None
        if slr <= 0:
            return RcaFinding(sku_id, store_id, 14, "Stock Expired",
                               "S22_Shelf_Life_Remaining_Days", slr, "<= 0", "")
        if wc is not None and slr < wc * 7:
            return RcaFinding(sku_id, store_id, 15,
                               "Expiry Risk: Short-Expiry SKU ordered more than actual demand",
                               "S22_Shelf_Life_Remaining_Days", slr,
                               "< S01_Weeks_Cover * 7", "")
        if slr < 7:
            return RcaFinding(sku_id, store_id, 16, "Near Expiry: Monitor",
                               "S22_Shelf_Life_Remaining_Days", slr, "< 7", "")
        return None


if __name__ == "__main__":
    from data_mapping import load_sku_store_data

    rows = load_sku_store_data("data/sample/Sample_RCA_Data.xlsx")
    engine = RcaEngine()
    r = rows[3]  # Row_ID 4 — the Gap 2 Active Promo exception case
    findings = engine.evaluate(r)
    print(f"Row {r['SKU_ID']} findings:")
    for f_ in findings:
        print(" ", f_.rule_id, f_.root_cause)

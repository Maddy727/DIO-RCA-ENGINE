"""
store_action.py — Layer 5

Store Action decision-support module. Implements the sequential cascade
from config/store_action_rules.yaml EXACTLY as written — one traversal per
SKU-Store, no branching per RCA root cause (Gap 3, confirmed intentional
design, not to be redesigned into a multi-RCA tree).

This module is independent of rca_engine.py: it re-evaluates the raw
signals itself, per the confirmed design ("Demand and Supply problems are
handled through the Corrective Action mapping; Store Manager only acts
where there's a genuine store-level intervention opportunity").
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

import yaml

CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "config")


@dataclass
class StoreActionResult:
    sku_id: str
    store_id: str
    path_taken: str  # "Perishable" | "Non-perishable"
    recommendation: str
    decision_path: list[str] = field(default_factory=list)


def _f(row, key):
    v = row.get(key)
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return v


class StoreActionEngine:
    def __init__(self, config_dir: str = CONFIG_DIR):
        with open(os.path.join(config_dir, "store_action_rules.yaml")) as f:
            self.config = yaml.safe_load(f)

    def evaluate(self, row) -> StoreActionResult:
        sku_id = row["SKU_ID"]
        store_id = row["Store_ID"]
        is_perishable = _f(row, "S21_Is_Perishable") == 1

        if is_perishable:
            return self._evaluate_perishable(row, sku_id, store_id)
        return self._evaluate_non_perishable(row, sku_id, store_id)

    # ------------------------------------------------------------------
    def _peer_shortage_outcome(self, row, path: list[str]) -> str:
        psf = _f(row, "S14_Peer_Shortage_Flag")
        if psf == 1:
            path.append("Peer_Shortage_Flag == 1")
            return "Transfer Viable - Check with Network Planner and Execute"
        path.append("Peer_Shortage_Flag == 0")
        return "Markdown can be considered - check with Commercial Team and Execute"

    def _evaluate_non_perishable(self, row, sku_id, store_id) -> StoreActionResult:
        path: list[str] = []
        wc = _f(row, "S01_Weeks_Cover")
        wct = _f(row, "S01_Weeks_Cover_Target")

        # Step 1/2: High DIO Check
        path.append("Step1: High DIO Check")
        if wc is None or wct is None or wc <= 1.1 * wct:
            return StoreActionResult(sku_id, store_id, "Non-perishable", "No Action Required", path)

        # Step 3/4: Phantom Inventory Check
        path.append("Step3: Phantom Inventory Check")
        if _f(row, "S02_Zero_Sales_Flag") == 1:
            return StoreActionResult(sku_id, store_id, "Non-perishable", "Recounting of SKU Required", path)

        # Step 5/6: Promo Context Check
        path.append("Step5: Promo Context Check")
        if _f(row, "S03_Active_Promo_Flag") == 1:
            return StoreActionResult(
                sku_id, store_id, "Non-perishable",
                "No Action — monitor post-promo velocity from Day 1 after promo ends", path,
            )

        # Step 7/8: Upcoming Promo Check
        path.append("Step7: Upcoming Promo Check")
        dtps = _f(row, "S04_Days_To_Promo_Start")
        upf = _f(row, "S04_Upcoming_Promo_Flag")
        if dtps is not None and dtps <= 14 and upf == 1:
            return StoreActionResult(
                sku_id, store_id, "Non-perishable",
                "No Action — monitor post-promo velocity from Day 1 after promo ends", path,
            )

        # Step 9: Previous Promo Check
        path.append("Step9: Previous Promo Check")
        dspe = _f(row, "S06_Days_Since_Promo_Ended")
        ppvr = _f(row, "S07_Post_Promo_Velocity_Ratio")
        if dspe is not None and ppvr is not None and dspe > 7 and ppvr < 0.5:
            recommendation = self._peer_shortage_outcome(row, path)
            return StoreActionResult(sku_id, store_id, "Non-perishable", recommendation, path)

        # Step 10: Season End Check
        path.append("Step10: Season End Check")
        asf = _f(row, "S08_Active_Season_Flag")
        dtse = _f(row, "S09_Days_To_Season_End")
        if asf == 1 and dtse is not None and dtse <= wc * 7:
            recommendation = self._peer_shortage_outcome(row, path)
            return StoreActionResult(sku_id, store_id, "Non-perishable", recommendation, path)

        # Step 11: Network Imbalance Check (Peer DIO)
        path.append("Step11: Network Imbalance Check (Peer DIO)")
        pdio = _f(row, "S12_Peer_DIO_Rate")
        if pdio is not None and pdio > 1.5:
            psf = _f(row, "S14_Peer_Shortage_Flag")
            if psf == 1:
                path.append("Peer_Shortage_Flag == 1")
                return StoreActionResult(
                    sku_id, store_id, "Non-perishable",
                    "Transfer Viable - Check with Network Planner and Execute", path,
                )
            path.append("Peer_Shortage_Flag == 0")
            return StoreActionResult(
                sku_id, store_id, "Non-perishable",
                "To decide among Transfer to distant Store or Markdown or Do-nothing", path,
            )

        # Step 12: Network Imbalance Check (Format DIO)
        path.append("Step12: Network Imbalance Check (Format DIO)")
        fdio = _f(row, "S13_Format_DIO_Ratio")
        if fdio is not None and fdio > 1.5:
            psf = _f(row, "S14_Peer_Shortage_Flag")
            if psf == 1:
                path.append("Peer_Shortage_Flag == 1")
                return StoreActionResult(
                    sku_id, store_id, "Non-perishable",
                    "Transfer Viable - Check with Network Planner and Execute", path,
                )
            path.append("Peer_Shortage_Flag == 0")
            return StoreActionResult(
                sku_id, store_id, "Non-perishable",
                "To decide among Transfer to distant Store or Markdown or Do-nothing", path,
            )

        # Format DIO Ratio <= 1.5 -> terminal, per Store_Action.xlsx C26 else-branch
        path.append("Format_DIO_Ratio <= 1.5")
        return StoreActionResult(
            sku_id, store_id, "Non-perishable",
            "To decide among Transfer to distant Store or Markdown or Do-nothing", path,
        )

    def _evaluate_perishable(self, row, sku_id, store_id) -> StoreActionResult:
        path: list[str] = ["Step1: Perishable path (S21_Is_Perishable == 1)"]
        wc = _f(row, "S01_Weeks_Cover")
        slr = _f(row, "S22_Shelf_Life_Remaining_Days")

        path.append("Step2: Shelf Life vs 0")
        if slr is not None and slr <= 0:
            return StoreActionResult(sku_id, store_id, "Perishable", "Remove from Shelf", path)

        path.append("Step3: Shelf Life vs Weeks Cover x7")
        if slr is not None and wc is not None and slr <= wc * 7:
            return StoreActionResult(
                sku_id, store_id, "Perishable",
                "Store Manager to decide between Markdown/Transfer/Dispose/Donate for expiry-risk SKU", path,
            )

        path.append("Step4: Shelf Life vs 7 days")
        if slr is not None and slr <= 7:
            # "inventory will sell before expiry, Store Manager to monitor" then
            # follow Non-perishable Store Action Rules to find Root Cause.
            non_perishable_result = self._evaluate_non_perishable(row, sku_id, store_id)
            path.extend(non_perishable_result.decision_path)
            combined = (
                "inventory will sell before expiry, Store Manager to monitor; then: "
                f"{non_perishable_result.recommendation}"
            )
            return StoreActionResult(sku_id, store_id, "Perishable", combined, path)

        # Shelf life > 7 days for all batches -> follow Non-perishable Store Action Rules
        non_perishable_result = self._evaluate_non_perishable(row, sku_id, store_id)
        path.extend(non_perishable_result.decision_path)
        return StoreActionResult(
            sku_id, store_id, "Perishable", non_perishable_result.recommendation, path,
        )


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from data_mapping import load_sku_store_data

    rows = load_sku_store_data("data/sample/Sample_RCA_Data.xlsx")
    engine = StoreActionEngine()
    for r in rows[:5]:
        res = engine.evaluate(r)
        print(f"{res.sku_id:16s} [{res.path_taken:14s}] -> {res.recommendation}")

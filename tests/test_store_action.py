"""
test_store_action.py

No ground-truth column exists for Store Action outputs (unlike RCA), so
this is a spot-check against representative rows with manually-verified
expected outcomes, rather than an exhaustive 70-row regression.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "engine"))

from data_mapping import load_sku_store_data  # noqa: E402
from store_action import StoreActionEngine  # noqa: E402

DATA_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "Sample_RCA_Data_70row_ValidationBaseline.xlsx")


def test_gate_closed_non_perishable_no_action():
    rows = load_sku_store_data(DATA_PATH)
    engine = StoreActionEngine()
    # Any row where the gate is closed and it's non-perishable should get "No Action Required"
    # (none exist in the 70-row sample with gate closed + non-perishable, so this is a synthetic check)
    from types import SimpleNamespace

    class FakeRow(dict):
        def get(self, key, default=None):
            return dict.get(self, key, default)

        def __getitem__(self, key):
            return dict.get(self, key)

    row = FakeRow({"SKU_ID": "TEST", "Store_ID": "S1", "S01_Weeks_Cover": 1.0,
                    "S01_Weeks_Cover_Target": 1.0, "S21_Is_Perishable": 0})
    result = engine.evaluate(row)
    assert result.recommendation == "No Action Required", result.recommendation
    print("test_gate_closed_non_perishable_no_action: PASS")


def test_perishable_expired_bypasses_gate():
    rows = load_sku_store_data(DATA_PATH)
    engine = StoreActionEngine()
    row = [r for r in rows if r["SKU_ID"] == "SKU_FRSH_P01"][0]  # WC=0, Shelf Life=0
    result = engine.evaluate(row)
    assert result.recommendation == "Remove from Shelf", result.recommendation
    assert result.path_taken == "Perishable"
    print("test_perishable_expired_bypasses_gate: PASS")


def test_active_promo_halts_non_perishable_traversal():
    rows = load_sku_store_data(DATA_PATH)
    engine = StoreActionEngine()
    row = [r for r in rows if r["SKU_ID"] == "SKU_BWS_001"][0]  # Active Promo = 1
    result = engine.evaluate(row)
    assert "monitor post-promo velocity" in result.recommendation
    print("test_active_promo_halts_non_perishable_traversal: PASS")


def test_every_row_produces_exactly_one_result():
    rows = load_sku_store_data(DATA_PATH)
    engine = StoreActionEngine()
    for row in rows:
        result = engine.evaluate(row)
        assert result.recommendation, f"{row['SKU_ID']} produced no recommendation"
        assert result.path_taken in ("Perishable", "Non-perishable")
    print(f"test_every_row_produces_exactly_one_result: PASS ({len(rows)} rows)")


def test_peer_dio_step11_uses_correct_outcome_mapping():
    """
    Regression test for a real bug found in production use (SKU_CHD_P03,
    reported 2026-08-12): Step 11 (Network Imbalance Check - Peer DIO) was
    incorrectly reusing Step 9/10's outcome text ("Markdown can be
    considered...") instead of its own config-defined outcome ("To decide
    among Transfer to distant Store or Markdown or Do-nothing") when
    Peer_Shortage_Flag == 0. Verified against config/store_action_rules.yaml
    Step 11's peer_shortage_outcomes, which was always correct — only the
    Python evaluator had the bug.
    """
    rows = load_sku_store_data(DATA_PATH)
    engine = StoreActionEngine()
    known_affected_skus = ["SKU_CHD_P03", "SKU_AMB_006", "SKU_HB_005", "SKU_FRZ_004", "SKU_AMB_008"]
    for sku in known_affected_skus:
        row = [r for r in rows if r["SKU_ID"] == sku][0]
        result = engine.evaluate(row)
        assert result.recommendation == "To decide among Transfer to distant Store or Markdown or Do-nothing", (
            f"{sku}: expected 'To decide among Transfer to distant Store or Markdown or Do-nothing', "
            f"got {result.recommendation!r}"
        )
    print(f"test_peer_dio_step11_uses_correct_outcome_mapping: PASS ({len(known_affected_skus)} known-affected SKUs verified)")


if __name__ == "__main__":
    test_gate_closed_non_perishable_no_action()
    test_perishable_expired_bypasses_gate()
    test_active_promo_halts_non_perishable_traversal()
    test_every_row_produces_exactly_one_result()
    test_peer_dio_step11_uses_correct_outcome_mapping()
    print("\nAll store action module tests PASSED")

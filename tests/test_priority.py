"""
test_priority.py

The real 70-row sample has exactly ONE SKU per store, so it can only ever
exercise the small-population fallback (every store's eligible population
is 1, which is < 4). This test builds a synthetic multi-SKU-per-store
scenario to independently validate the percentile-based branch.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "engine"))

from priority import PriorityEngine  # noqa: E402


class FakeRow(dict):
    def get(self, key, default=None):
        return dict.get(self, key, default)

    def __getitem__(self, key):
        return dict.get(self, key)


def make_row(sku_id, store_id, wc, wct, slr=-1, dtse=-1):
    return FakeRow({
        "SKU_ID": sku_id, "Store_ID": store_id,
        "S01_Weeks_Cover": wc, "S01_Weeks_Cover_Target": wct,
        "S22_Shelf_Life_Remaining_Days": slr, "S09_Days_To_Season_End": dtse,
    })


def test_small_population_fallback():
    engine = PriorityEngine()
    # 2 eligible rows in the same store -> below threshold of 4 -> fallback
    rows = [
        make_row("A", "STORE_X", wc=5, wct=2),
        make_row("B", "STORE_X", wc=6, wct=2),
    ]
    fin = {
        ("A", "STORE_X"): {"Gross_Margin_Pct": 0.10, "Excess_Value": 1000},
        ("B", "STORE_X"): {"Gross_Margin_Pct": 0.40, "Excess_Value": 50},
    }
    results = engine.compute_all(rows, fin)
    assert len(results) == 2
    for r in results:
        assert r.margin_score == 3.0
        assert r.excess_value_score == 3.0
        assert r.margin_percentile_within_store is None
        assert r.excess_value_percentile_within_store is None
        assert r.store_eligible_population_size == 2
    print("test_small_population_fallback: PASS")


def test_percentile_branch_low_margin_high_score():
    engine = PriorityEngine()
    # 5 eligible rows in the same store -> at/above threshold of 4 -> real percentile calc
    skus = ["A", "B", "C", "D", "E"]
    margins = [0.05, 0.15, 0.25, 0.35, 0.45]  # ascending margin
    excess_values = [10, 20, 30, 40, 5000]     # E is a huge outlier -> should get top Excess Value score
    rows = [make_row(s, "STORE_Y", wc=5, wct=2) for s in skus]
    fin = {
        (s, "STORE_Y"): {"Gross_Margin_Pct": m, "Excess_Value": v}
        for s, m, v in zip(skus, margins, excess_values)
    }
    results = {r.sku_id: r for r in engine.compute_all(rows, fin)}

    # Lowest margin (A, 0.05) should get the HIGHEST margin score (lowest percentile -> high score)
    assert results["A"].margin_score == max(r.margin_score for r in results.values()), \
        f"Expected A (lowest margin) to have the highest margin score, got {results['A'].margin_score}"
    # Highest margin (E, 0.45) should get the LOWEST margin score
    assert results["E"].margin_score == min(r.margin_score for r in results.values())
    # Highest excess value (E, 5000) should get the HIGHEST excess value score
    assert results["E"].excess_value_score == max(r.excess_value_score for r in results.values())
    # Lowest excess value (A, 10) should get the LOWEST excess value score
    assert results["A"].excess_value_score == min(r.excess_value_score for r in results.values())
    # Percentile fields should be populated (not None) since pop >= 4
    for r in results.values():
        assert r.margin_percentile_within_store is not None
        assert r.excess_value_percentile_within_store is not None
        assert r.store_eligible_population_size == 5
    print("test_percentile_branch_low_margin_high_score: PASS")


def test_percentile_is_within_store_not_network():
    """Two stores with different margin distributions must score independently."""
    engine = PriorityEngine()
    rows = [
        make_row("A1", "STORE_1", wc=5, wct=2), make_row("A2", "STORE_1", wc=5, wct=2),
        make_row("A3", "STORE_1", wc=5, wct=2), make_row("A4", "STORE_1", wc=5, wct=2),
        make_row("B1", "STORE_2", wc=5, wct=2), make_row("B2", "STORE_2", wc=5, wct=2),
        make_row("B3", "STORE_2", wc=5, wct=2), make_row("B4", "STORE_2", wc=5, wct=2),
    ]
    # STORE_1: margins 0.10-0.40 (A1 lowest). STORE_2: margins 0.50-0.80 (B1 lowest, but
    # much higher in absolute terms than any STORE_1 SKU). If scoring were network-wide,
    # B1 (0.50) would NOT be the bottom percentile since every STORE_1 value is lower.
    # If scoring is correctly within-store, B1 still gets the top margin score within STORE_2.
    fin = {
        ("A1", "STORE_1"): {"Gross_Margin_Pct": 0.10, "Excess_Value": 100},
        ("A2", "STORE_1"): {"Gross_Margin_Pct": 0.20, "Excess_Value": 100},
        ("A3", "STORE_1"): {"Gross_Margin_Pct": 0.30, "Excess_Value": 100},
        ("A4", "STORE_1"): {"Gross_Margin_Pct": 0.40, "Excess_Value": 100},
        ("B1", "STORE_2"): {"Gross_Margin_Pct": 0.50, "Excess_Value": 100},
        ("B2", "STORE_2"): {"Gross_Margin_Pct": 0.60, "Excess_Value": 100},
        ("B3", "STORE_2"): {"Gross_Margin_Pct": 0.70, "Excess_Value": 100},
        ("B4", "STORE_2"): {"Gross_Margin_Pct": 0.80, "Excess_Value": 100},
    }
    results = {r.sku_id: r for r in engine.compute_all(rows, fin)}
    assert results["B1"].margin_score == max(r.margin_score for r in results.values() if r.store_id == "STORE_2"), \
        "B1 should get the top margin score WITHIN STORE_2 despite being higher-margin than all of STORE_1"
    assert results["A1"].margin_score == max(r.margin_score for r in results.values() if r.store_id == "STORE_1")
    print("test_percentile_is_within_store_not_network: PASS")


if __name__ == "__main__":
    test_small_population_fallback()
    test_percentile_branch_low_margin_high_score()
    test_percentile_is_within_store_not_network()
    print("\nAll priority module tests PASSED")

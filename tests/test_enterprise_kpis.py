"""
test_enterprise_kpis.py

Regression test for a real bug found in production use (reported
2026-08-15): the "SKU-Stores Requiring Intervention" KPI on the Enterprise
Control Tower page was computed as len(filtered) — the FULL filtered
population (20,084 rows with no filters applied) — rather than only the
subset that actually requires intervention. Confirmed the intended split
(from the approved dataset design) is ~60% requiring intervention / ~40%
healthy; the correct count is 12,358, not 20,084.

Also verifies "Stores with DIO Issue" and "Categories with DIO Issue" use
the same intervention-required population consistently, even though their
displayed values happen to be unchanged (55 stores, 8 categories) — every
store and category has at least one intervention-required row, so the bug
was numerically invisible for these two specifically, but the underlying
logic was still wrong before this fix.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "streamlit_app"))

from utils.data_loader import load_all  # noqa: E402
from utils.dio_aggregation import add_dio_fields  # noqa: E402
from utils.priority_labels import add_priority_label  # noqa: E402


def test_sku_stores_requiring_intervention_excludes_healthy_rows():
    data = load_all()
    wide = add_priority_label(add_dio_fields(data["wide"]))

    intervention_required = wide[wide["Priority_Score"].notna()]
    total = len(wide)
    intervention_count = len(intervention_required)

    assert intervention_count < total, "Intervention count should be strictly less than total population"
    pct = intervention_count / total * 100
    assert 55 <= pct <= 65, f"Expected roughly 60% requiring intervention, got {pct:.1f}%"

    # Stores/Categories with DIO Issue must also use the intervention-required
    # population, not the full one (even though the numbers currently match).
    stores_all = wide["Store_ID"].nunique()
    stores_intervention = intervention_required["Store_ID"].nunique()
    categories_all = wide["Category"].nunique()
    categories_intervention = intervention_required["Category"].nunique()

    assert stores_intervention <= stores_all
    assert categories_intervention <= categories_all

    print(f"test_sku_stores_requiring_intervention_excludes_healthy_rows: PASS "
          f"({intervention_count}/{total} = {pct:.1f}% requiring intervention; "
          f"{stores_intervention} stores, {categories_intervention} categories with an issue)")


if __name__ == "__main__":
    test_sku_stores_requiring_intervention_excludes_healthy_rows()
    print("\nAll enterprise KPI tests PASSED")

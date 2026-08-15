"""
test_owner_actions.py

Validates the two core guarantees of the Action Owner feature (added
2026-08-14), using the real 542-row "same owner, multiple causes" case
identified during design discussion:
  1. owner_scoped_sku_store_keys() de-duplicates — a SKU-Store with 2+
     causes owned by the same person appears exactly once in the scoped
     population, not once per cause.
  2. owner_action_items() does NOT de-duplicate — it deliberately shows
     one row per actual root cause, even when that means the same
     Excess_Value appears more than once for the same SKU-Store (by
     design — see components/owner_actions.py's docstring).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "streamlit_app"))

from utils.data_loader import load_all  # noqa: E402
from utils.dio_aggregation import add_dio_fields  # noqa: E402
from utils.priority_labels import add_priority_label  # noqa: E402
from utils.aggregations import owner_scoped_sku_store_keys, owner_action_items  # noqa: E402


def test_population_scoping_deduplicates_multi_cause_sku_stores():
    data = load_all()
    ca = data["corrective_action_long"]

    # Find a real SKU-Store with 2+ causes owned by the SAME person
    grouped = ca.groupby(["SKU_ID", "Store_ID", "Action_Owner"]).size().reset_index(name="n")
    multi = grouped[grouped["n"] > 1].iloc[0]
    owner = multi["Action_Owner"]

    keys = owner_scoped_sku_store_keys(ca, owner)
    match_count = ((keys["SKU_ID"] == multi["SKU_ID"]) & (keys["Store_ID"] == multi["Store_ID"])).sum()
    assert match_count == 1, (
        f"{multi['SKU_ID']}@{multi['Store_ID']} has {multi['n']} causes owned by {owner} "
        f"but appeared {match_count} times in the scoped population (expected exactly 1)"
    )
    print(f"test_population_scoping_deduplicates_multi_cause_sku_stores: PASS "
          f"({multi['SKU_ID']}@{multi['Store_ID']}, {multi['n']} causes -> 1 population entry)")


def test_action_items_shows_one_row_per_cause_not_deduplicated():
    data = load_all()
    wide = add_priority_label(add_dio_fields(data["wide"]))
    ca = data["corrective_action_long"]

    grouped = ca.groupby(["SKU_ID", "Store_ID", "Action_Owner"]).size().reset_index(name="n")
    multi = grouped[grouped["n"] > 1].iloc[0]
    owner = multi["Action_Owner"]

    items = owner_action_items(ca, data["master"], data["financial"], wide, owner)
    match_count = ((items["SKU_ID"] == multi["SKU_ID"]) & (items["Store_ID"] == multi["Store_ID"])).sum()
    assert match_count == multi["n"], (
        f"Expected {multi['n']} action item rows for {multi['SKU_ID']}@{multi['Store_ID']}, got {match_count}"
    )
    # And the Excess_Value should be IDENTICAL across those rows (same SKU-Store, same context value)
    values = items[(items["SKU_ID"] == multi["SKU_ID"]) & (items["Store_ID"] == multi["Store_ID"])]["Excess_Value"]
    assert values.nunique() == 1, "Excess_Value should be identical across rows for the same SKU-Store"

    print(f"test_action_items_shows_one_row_per_cause_not_deduplicated: PASS "
          f"({multi['SKU_ID']}@{multi['Store_ID']}: {match_count} rows, consistent Excess_Value)")


if __name__ == "__main__":
    test_population_scoping_deduplicates_multi_cause_sku_stores()
    test_action_items_shows_one_row_per_cause_not_deduplicated()
    print("\nAll owner actions tests PASSED")

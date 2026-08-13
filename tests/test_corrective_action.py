"""
test_corrective_action.py

Validates: (1) output row count exactly matches RCA finding count (no
aggregation/dedup), (2) every root cause in the 70-row sample except
"No Action Required" has a non-null mapping.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "engine"))

from data_mapping import load_sku_store_data  # noqa: E402
from rca_engine import RcaEngine  # noqa: E402
from corrective_action import CorrectiveActionAssembler  # noqa: E402

DATA_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "Sample_RCA_Data_70row_ValidationBaseline.xlsx")


def test_row_count_matches_and_no_unmapped_causes():
    rows = load_sku_store_data(DATA_PATH)
    rca = RcaEngine()
    assembler = CorrectiveActionAssembler()

    total_findings = 0
    total_results = 0
    unmapped = []

    for row in rows:
        findings = rca.evaluate(row)
        results = assembler.assemble(findings)
        assert len(findings) == len(results), f"{row['SKU_ID']}: row count mismatch"
        total_findings += len(findings)
        total_results += len(results)
        for r in results:
            if r.corrective_action is None and r.root_cause != "No Action Required":
                unmapped.append((r.sku_id, r.root_cause))

    assert total_findings == total_results
    assert not unmapped, f"Unexpected unmapped root causes: {unmapped}"
    print(f"test_row_count_matches_and_no_unmapped_causes: PASS "
          f"({total_findings} findings -> {total_results} corrective action rows)")


def test_multi_root_cause_gets_multiple_owners():
    rows = load_sku_store_data(DATA_PATH)
    rca = RcaEngine()
    assembler = CorrectiveActionAssembler()

    row = [r for r in rows if r["SKU_ID"] == "SKU_FRSH_001"][0]
    findings = rca.evaluate(row)
    results = assembler.assemble(findings)
    owners = {r.action_owner for r in results}
    assert len(results) > 1, "Expected multiple root causes for this row"
    assert len(owners) > 1, f"Expected multiple distinct owners, got {owners}"
    print(f"test_multi_root_cause_gets_multiple_owners: PASS ({len(results)} rows, owners={owners})")


if __name__ == "__main__":
    test_row_count_matches_and_no_unmapped_causes()
    test_multi_root_cause_gets_multiple_owners()
    print("\nAll corrective action module tests PASSED")

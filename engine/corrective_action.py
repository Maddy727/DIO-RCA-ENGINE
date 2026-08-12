"""
corrective_action.py — Layer 6

Pure join: RCA findings -> Corrective Action / Action Owner / Review Owner /
Dashboard View, sourced verbatim from config/corrective_action_map.yaml.
One output row per fired root cause — never aggregated or deduplicated, so
a SKU-Store with 4 root causes yields 4 rows here, potentially with 4
different owners (Principle #15).
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import yaml

CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "config")


@dataclass
class CorrectiveActionResult:
    sku_id: str
    store_id: str
    root_cause: str
    corrective_action: str | None
    action_owner: str | None
    review_owner: str | None
    dashboard_view: str | None


def load_corrective_action_map(config_dir: str = CONFIG_DIR) -> dict[str, dict]:
    """Returns {root_cause.lower(): {Corrective Action, Action Owner, Review Owner, Dashboard View}}."""
    with open(os.path.join(config_dir, "corrective_action_map.yaml")) as f:
        cfg = yaml.safe_load(f)
    return {
        m["Root Cause"].lower(): {
            "Corrective Action": m["Corrective Action"],
            "Action Owner": m["Action Owner"],
            "Review Owner": m["Review Owner"],
            "Dashboard View": m["Dashboard View"],
        }
        for m in cfg["mappings"]
    }


class CorrectiveActionAssembler:
    def __init__(self, config_dir: str = CONFIG_DIR):
        self.map = load_corrective_action_map(config_dir)

    def assemble(self, findings) -> list[CorrectiveActionResult]:
        """
        findings: list of rca_engine.RcaFinding for ONE SKU-Store.
        Returns one CorrectiveActionResult per finding. Findings with no
        mapping (only "No Action Required" should ever hit this) pass
        through with None fields rather than being silently dropped.
        """
        results = []
        for finding in findings:
            mapping = self.map.get(finding.root_cause.lower())
            if mapping is None:
                results.append(CorrectiveActionResult(
                    finding.sku_id, finding.store_id, finding.root_cause,
                    None, None, None, None,
                ))
            else:
                results.append(CorrectiveActionResult(
                    finding.sku_id, finding.store_id, finding.root_cause,
                    mapping["Corrective Action"], mapping["Action Owner"],
                    mapping["Review Owner"], mapping["Dashboard View"],
                ))
        return results


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from data_mapping import load_sku_store_data
    from rca_engine import RcaEngine

    rows = load_sku_store_data("data/sample/Sample_RCA_Data.xlsx")
    rca = RcaEngine()
    assembler = CorrectiveActionAssembler()

    # Row with multiple root causes -> multiple corrective action rows
    row = [r for r in rows if r["SKU_ID"] == "SKU_FRSH_001"][0]
    findings = rca.evaluate(row)
    results = assembler.assemble(findings)
    print(f"{row['SKU_ID']}: {len(findings)} root causes -> {len(results)} corrective action rows")
    for r in results:
        print(f"  {r.root_cause:55s} owner={r.action_owner}")

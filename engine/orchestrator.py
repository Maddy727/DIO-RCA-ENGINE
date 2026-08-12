"""
orchestrator.py — Integration layer

Wires the four independently-validated modules together and produces the
four output datasets described in the architecture doc:
  1. RCA output              (data/outputs/rca_output.csv)
  2. Store Action output     (data/outputs/store_action_output.csv)
  3. Corrective Action output(data/outputs/corrective_action_output.csv)
  4. Priority output         (data/outputs/priority_output.csv)

Each dataset is written independently — this script does NOT merge them
into a single "final verdict" table, per the separation-of-concerns
principle. Any such merge is a presentation-layer concern (future
Streamlit), not an engine concern.
"""
from __future__ import annotations

import csv
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from data_mapping import load_sku_store_data, load_financial_impact_data  # noqa: E402
from rca_engine import RcaEngine  # noqa: E402
from problem_area import ProblemAreaTagger  # noqa: E402
from store_action import StoreActionEngine  # noqa: E402
from corrective_action import CorrectiveActionAssembler  # noqa: E402
from priority import PriorityEngine  # noqa: E402

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
SAMPLE_DATA = os.path.join(PROJECT_ROOT, "data", "sample", "Sample_RCA_Data.xlsx")
FINANCIAL_DATA = os.path.join(PROJECT_ROOT, "data", "sample", "Financial_Impact_Data.xlsx")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "data", "outputs")


def write_csv(path: str, rows: list[dict]):
    if not rows:
        print(f"  (no rows to write for {path})")
        return
    # utf-8-sig: adds a BOM so Excel (and other tools that guess encoding
    # instead of assuming UTF-8) correctly detect UTF-8 and render special
    # characters like em dashes correctly instead of as mojibake.
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"  wrote {len(rows)} rows -> {path}")


def run(sample_data_path: str = SAMPLE_DATA, financial_data_path: str = FINANCIAL_DATA,
        output_dir: str = OUTPUT_DIR):
    os.makedirs(output_dir, exist_ok=True)

    print("Loading input data...")
    rows = load_sku_store_data(sample_data_path)
    financial_lookup = load_financial_impact_data(financial_data_path)
    print(f"  {len(rows)} SKU-Store rows, {len(financial_lookup)} financial records")

    rca_engine = RcaEngine()
    problem_area_tagger = ProblemAreaTagger()
    store_action_engine = StoreActionEngine()
    corrective_action_assembler = CorrectiveActionAssembler()
    priority_engine = PriorityEngine()

    # ---- 1. RCA output + Problem Area ----
    print("\n[1/4] Running RCA Engine + Problem Area tagging...")
    rca_output_rows = []
    all_findings_by_row = {}  # (sku, store) -> list[RcaFinding], for downstream reuse
    for row in rows:
        findings = rca_engine.evaluate(row)
        all_findings_by_row[(row["SKU_ID"], row["Store_ID"])] = findings
        for f in findings:
            rca_output_rows.append({
                "SKU_ID": f.sku_id, "Store_ID": f.store_id, "Rule_ID": f.rule_id,
                "Root_Cause": f.root_cause,
                "Problem_Area": problem_area_tagger.tag(f.root_cause),
                "Triggering_Signal": f.triggering_signal, "Signal_Value": f.signal_value,
                "Threshold_Applied": f.threshold_applied, "Gate_Status": f.gate_status,
            })
    write_csv(os.path.join(output_dir, "rca_output.csv"), rca_output_rows)

    # ---- 2. Store Action output ----
    print("\n[2/4] Running Store Action module...")
    store_action_rows = []
    for row in rows:
        result = store_action_engine.evaluate(row)
        store_action_rows.append({
            "SKU_ID": result.sku_id, "Store_ID": result.store_id,
            "Path_Taken": result.path_taken,
            "Store_Action_Recommendation": result.recommendation,
            "Decision_Path": " -> ".join(result.decision_path),
        })
    write_csv(os.path.join(output_dir, "store_action_output.csv"), store_action_rows)

    # ---- 3. Corrective Action output ----
    print("\n[3/4] Running Corrective Action assembly...")
    corrective_action_rows = []
    for row in rows:
        findings = all_findings_by_row[(row["SKU_ID"], row["Store_ID"])]
        results = corrective_action_assembler.assemble(findings)
        for r in results:
            corrective_action_rows.append({
                "SKU_ID": r.sku_id, "Store_ID": r.store_id, "Root_Cause": r.root_cause,
                "Corrective_Action": r.corrective_action, "Action_Owner": r.action_owner,
                "Review_Owner": r.review_owner, "Dashboard_View": r.dashboard_view,
            })
    write_csv(os.path.join(output_dir, "corrective_action_output.csv"), corrective_action_rows)

    # ---- 4. Priority output ----
    print("\n[4/4] Running Priority module...")
    eligible_rows = [
        row for row in rows
        if any(f.root_cause != "No Action Required"
               for f in all_findings_by_row[(row["SKU_ID"], row["Store_ID"])])
    ]
    print(f"  Eligible (DIO intervention population): {len(eligible_rows)} / {len(rows)}")
    priority_results = priority_engine.compute_all(eligible_rows, financial_lookup)
    priority_rows = [{
        "SKU_ID": r.sku_id, "Store_ID": r.store_id,
        "Urgency_Score": r.urgency_score, "DIO_Severity_Score": r.dio_severity_score,
        "Margin_Score": r.margin_score, "Excess_Value_Score": r.excess_value_score,
        "Margin_Percentile_Within_Store": r.margin_percentile_within_store,
        "Excess_Value_Percentile_Within_Store": r.excess_value_percentile_within_store,
        "Store_Eligible_Population_Size": r.store_eligible_population_size,
        "Priority_Score": r.priority_score,
    } for r in priority_results]
    write_csv(os.path.join(output_dir, "priority_output.csv"), priority_rows)

    print("\nDone. Four independent output datasets written to data/outputs/.")
    return {
        "rca_output": rca_output_rows,
        "store_action_output": store_action_rows,
        "corrective_action_output": corrective_action_rows,
        "priority_output": priority_rows,
    }


if __name__ == "__main__":
    run()

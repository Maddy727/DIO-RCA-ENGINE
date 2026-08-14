"""
test_task_cards.py

Regression test for a real bug found in production use (reported via
SKU_FRO_0094 and SKU_FRO_0095 at Express Aberdeen, 2026-08-14): the
"Perishable Expiry Risk" Store Manager task card was matching on
Path_Taken == "Perishable" alone, which incorrectly included perishable
SKUs whose actual recommendation was unrelated to expiry (e.g. "No Action
Required") — because a perishable item with plenty of shelf life left
falls through to the non-perishable evaluation (see engine/store_action.py
Step 4's else-branch) while Path_Taken still reports "Perishable".

Fixed to match only the two recommendation strings the engine actually
produces when shelf life itself is the trigger.
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "streamlit_app"))

from utils.data_loader import load_all  # noqa: E402
from utils.dio_aggregation import add_dio_fields  # noqa: E402
from components.task_cards import TASK_GROUP_DEFINITIONS  # noqa: E402


def test_perishable_expiry_risk_excludes_no_action_required():
    data = load_all()
    wide = add_dio_fields(data["wide"])
    group = next(g for g in TASK_GROUP_DEFINITIONS if g["title"] == "Perishable Expiry Risk")
    matched = wide[group["match"](wide)]

    # None of the matched rows should ever be "No Action Required" or any
    # other non-expiry-driven recommendation.
    allowed = {"Remove from Shelf", "Store Manager to decide between Markdown/Transfer/Dispose/Donate for expiry-risk SKU"}
    bad = matched[~matched["Store_Action_Recommendation"].isin(allowed)]
    assert bad.empty, f"Perishable Expiry Risk card matched non-expiry rows: {bad['Store_Action_Recommendation'].unique()}"

    # The two specifically-reported SKUs must not appear, regardless of store.
    reported_skus = {"SKU_FRO_0094", "SKU_FRO_0095"}
    still_matched = set(matched["SKU_ID"]) & reported_skus
    # (These SKUs CAN legitimately appear if some OTHER store instance of them
    # genuinely has an expiry-driven recommendation — the check that matters
    # is that every matched row has an expiry-driven recommendation, done above.
    # This second check just confirms the specific reported case is now correct.)
    express_aberdeen = wide[wide["Store_Name"] == "Express Aberdeen"]
    aberdeen_matched = express_aberdeen[group["match"](express_aberdeen)]
    aberdeen_bad_skus = set(aberdeen_matched["SKU_ID"]) & reported_skus
    assert not aberdeen_bad_skus, f"Reported SKUs still incorrectly matched at Express Aberdeen: {aberdeen_bad_skus}"

    print(f"test_perishable_expiry_risk_excludes_no_action_required: PASS "
          f"({len(matched)} genuinely expiry-driven rows across the dataset)")


def test_task_card_badge_logic():
    """
    Regression test for the badge logic agreed 2026-08-14:
      - Perishable Expiry Risk: Emergency if ANY matched SKU has
        S22_Shelf_Life_Remaining_Days <= 7, else Urgent.
      - Recount Required: always Urgent.
      - Monitor — Post-Promo: always Low.
      - All other groups: mean(Priority_Score), banded via priority_label().
    """
    from components.task_cards import _compute_task_card_label

    urgent_case = pd.DataFrame({"S22_Shelf_Life_Remaining_Days": [10.5, 20.0, 15.2]})
    assert _compute_task_card_label("Perishable Expiry Risk", urgent_case) == "Urgent"

    emergency_case = pd.DataFrame({"S22_Shelf_Life_Remaining_Days": [10.5, 6.9, 15.2]})
    assert _compute_task_card_label("Perishable Expiry Risk", emergency_case) == "Emergency"

    assert _compute_task_card_label("Recount Required", pd.DataFrame({"Priority_Score": [4.5]})) == "Urgent"
    assert _compute_task_card_label("Recount Required", pd.DataFrame({"Priority_Score": [0.9]})) == "Urgent"

    assert _compute_task_card_label("Monitor — Post-Promo", pd.DataFrame({"Priority_Score": [4.9]})) == "Low"
    assert _compute_task_card_label("Monitor — Post-Promo", pd.DataFrame({"Priority_Score": [0.9]})) == "Low"

    assert _compute_task_card_label("Transfer Viable", pd.DataFrame({"Priority_Score": [4.0, 5.0]})) == "Emergency"
    assert _compute_task_card_label("Markdown Recommended", pd.DataFrame({"Priority_Score": [0.9, 1.0]})) == "Low"

    print("test_task_card_badge_logic: PASS")


if __name__ == "__main__":
    test_perishable_expiry_risk_excludes_no_action_required()
    test_task_card_badge_logic()
    print("\nAll task card tests PASSED")

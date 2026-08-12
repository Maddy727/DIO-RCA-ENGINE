"""
problem_area.py — Layer 4

Pure lookup: Root Cause -> Problem Area (Demand / Supply / Network / Others).
Sourced from config/corrective_action_map.yaml (Column C, "Problem Area"),
which is transcribed verbatim from Root_Cause_-_Corrective_Action_-_Owner_-
Dashboard_View_Mapping.xlsx. No logic of its own — deliberately dumb, per
the separation-of-concerns principle.
"""
from __future__ import annotations

import os

import yaml

CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "config")


def load_problem_area_map(config_dir: str = CONFIG_DIR) -> dict[str, str]:
    """
    Returns {root_cause.lower(): Problem Area}.

    NOTE (technical, not a business-logic decision): the source Excel files
    disagree on capitalization for 3 root causes between RCA_Rules.xlsx and
    the Corrective Action mapping file:
      - "high forecast bias" (RCA_Rules)  vs "High Forecast Bias" (mapping)
      - "high stock vs peers" (RCA_Rules) vs "High stock vs peers" (mapping)
      - "High Stock vs Format" (RCA_Rules) vs "high stock vs format" (mapping)
    The join key is therefore normalized to lowercase here. This does not
    change any business rule or wording — the RCA engine's original casing
    is still what gets written to the Root_Cause output field; only the
    *lookup* into this mapping ignores case.
    """
    with open(os.path.join(config_dir, "corrective_action_map.yaml")) as f:
        cfg = yaml.safe_load(f)
    return {m["Root Cause"].lower(): m["Problem Area"] for m in cfg["mappings"]}


class ProblemAreaTagger:
    def __init__(self, config_dir: str = CONFIG_DIR):
        self.map = load_problem_area_map(config_dir)

    def tag(self, root_cause: str) -> str | None:
        """
        Returns the Problem Area for a root cause, or None if the root cause
        has no mapping (this should only ever be "No Action Required", which
        is a terminal gate outcome, not a true root cause).
        """
        return self.map.get(root_cause.lower())


if __name__ == "__main__":
    tagger = ProblemAreaTagger()
    for rc in ["Excess Supply", "high stock vs peers", "Active Promo", "No Action Required"]:
        print(f"{rc!r:55s} -> {tagger.tag(rc)}")

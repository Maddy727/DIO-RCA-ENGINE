"""
data_loader.py

Loads the FOUR validated engine outputs plus Sample_RCA_Data.xlsx (master
data + raw signals) and Financial_Impact_Data.xlsx, and joins them into
ready-to-use pandas dataframes.

THIS MODULE DOES NOT RUN THE ENGINE. It reads pre-generated CSVs from
data/outputs/ (written by engine/orchestrator.py) plus the two approved
Excel files. If data/outputs/ is missing or stale, run:
    python3 engine/orchestrator.py
from the project root before launching Streamlit.

Two grains are joined here, deliberately kept separate:
  - "wide" (one row per SKU-Store): master data + signals + financials +
    Store Action + Priority
  - "long" (many rows per SKU-Store): RCA findings + Corrective Action,
    one row per fired root cause

The wide table is used for KPIs/charts/rankings. The long table is used
for RCA Details / root-cause-level displays. They are joined on demand
(never flattened into one all-purpose table), consistent with the engine's
separation-of-concerns principle: a SKU-Store's multiple root causes are
never merged into a single row anywhere except as an explicit, clearly-
labelled presentation summary (see aggregations.summarize_root_causes).
"""
from __future__ import annotations

import os

import openpyxl
import pandas as pd
import streamlit as st

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
SAMPLE_DATA_PATH = os.path.join(PROJECT_ROOT, "data", "sample", "Sample_RCA_Data.xlsx")
FINANCIAL_DATA_PATH = os.path.join(PROJECT_ROOT, "data", "sample", "Financial_Impact_Data.xlsx")
OUTPUTS_DIR = os.path.join(PROJECT_ROOT, "data", "outputs")

JOIN_KEYS = ["SKU_ID", "Store_ID"]


@st.cache_data(show_spinner=False)
def _load_master_data() -> pd.DataFrame:
    """
    Master data + all 22 raw signals, from Sample_RCA_Data.xlsx (columns
    A-AG only). Uses the 'calamine' engine (fast Rust-based Excel parser)
    — measured ~10x faster than openpyxl at 20,000 rows.
    """
    df = pd.read_excel(SAMPLE_DATA_PATH, sheet_name=0, header=2, engine="calamine")
    df = df.dropna(how="all")
    df = df.iloc[:, :33]  # A..AG — excludes ground-truth columns AH-AL
    return df


@st.cache_data(show_spinner=False)
def _load_financial_data() -> pd.DataFrame:
    return pd.read_excel(FINANCIAL_DATA_PATH, sheet_name="Financial_Impact_Data", engine="calamine")


@st.cache_data(show_spinner=False)
def _load_engine_outputs() -> dict[str, pd.DataFrame]:
    """
    ALWAYS regenerates the 4 output CSVs by running the already-validated
    engine/orchestrator.py, rather than only regenerating when files are
    missing.

    Why: on Streamlit Community Cloud, a `git push` restarts the app but
    does NOT necessarily wipe files that were written to disk by a
    previous run (data/outputs/*.csv is gitignored, so it's never part of
    the fresh git pull — but if it was already written to disk by an
    earlier session, it can silently persist and get served instead of
    being regenerated from your latest engine code). Always regenerating
    here removes that entire class of "stale output survives a code fix"
    bug. This whole function is wrapped in @st.cache_data, so despite
    "always" regenerating, it still only actually runs ONCE per running
    app process (not on every filter change / page interaction) — so this
    does not reintroduce the "don't re-run the engine on every filter
    change" performance concern.
    """
    import sys
    engine_dir = os.path.join(PROJECT_ROOT, "engine")
    sys.path.insert(0, engine_dir)
    import orchestrator as engine_orchestrator
    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    engine_orchestrator.run(
        sample_data_path=SAMPLE_DATA_PATH,
        financial_data_path=FINANCIAL_DATA_PATH,
        output_dir=OUTPUTS_DIR,
    )

    required = ["rca_output.csv", "store_action_output.csv",
                "corrective_action_output.csv", "priority_output.csv"]
    missing = [f for f in required if not os.path.exists(os.path.join(OUTPUTS_DIR, f))]
    if missing:
        raise FileNotFoundError(f"Engine output file(s) still missing after running the orchestrator: {missing}.")

    return {
        "rca": pd.read_csv(os.path.join(OUTPUTS_DIR, "rca_output.csv")),
        "store_action": pd.read_csv(os.path.join(OUTPUTS_DIR, "store_action_output.csv")),
        "corrective_action": pd.read_csv(os.path.join(OUTPUTS_DIR, "corrective_action_output.csv")),
        "priority": pd.read_csv(os.path.join(OUTPUTS_DIR, "priority_output.csv")),
    }


@st.cache_data(show_spinner=False)
def load_all() -> dict[str, pd.DataFrame]:
    """
    Returns a dict of dataframes:
      'wide'              -- one row per SKU-Store: master data + signals + financials
                              + Store Action + Priority (+ DIO/DIO_Target/Inventory_Value/
                              Excess_Value presentation-level fields, see dio_aggregation.py)
      'rca_long'           -- one row per fired root cause (RCA output, unmodified)
      'corrective_action_long' -- one row per fired root cause (Corrective Action output, unmodified)
      'master'              -- master data + signals alone (for signal lookups)
      'financial'            -- financial data alone
    """
    master = _load_master_data()
    financial = _load_financial_data()
    outputs = _load_engine_outputs()

    wide = master.merge(financial, on=JOIN_KEYS, how="left")
    wide = wide.merge(outputs["store_action"], on=JOIN_KEYS, how="left")
    wide = wide.merge(outputs["priority"], on=JOIN_KEYS, how="left")

    return {
        "wide": wide,
        "rca_long": outputs["rca"],
        "corrective_action_long": outputs["corrective_action"],
        "master": master,
        "financial": financial,
    }


if __name__ == "__main__":
    data = load_all()
    for name, df in data.items():
        print(f"{name}: {df.shape}")
    print("\nwide columns:", list(data["wide"].columns))

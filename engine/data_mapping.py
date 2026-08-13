"""
data_mapping.py — Layer 1

Loads raw SKU-Store data (from Excel or CSV) and applies the column-mapping
config to produce rows in the canonical schema the rest of the engine
expects. This is the ONLY module that should know about client-specific
column names. Every other module deals exclusively in canonical field
names (SKU_ID, S01_Weeks_Cover, ...).

To onboard a new client: edit config/column_mapping.yaml, do not touch
this file or any downstream module.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import openpyxl
import pandas as pd
import yaml

CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "config")


@dataclass
class SkuStoreRow:
    """One canonical SKU-Store row. Attribute access mirrors canonical field names."""

    fields: dict[str, Any]

    def __getitem__(self, key: str) -> Any:
        return self.fields[key]

    def get(self, key: str, default=None) -> Any:
        return self.fields.get(key, default)


def load_column_mapping(config_dir: str = CONFIG_DIR) -> dict[str, str]:
    """Returns {canonical_field_name: source_column_name}."""
    with open(os.path.join(config_dir, "column_mapping.yaml")) as f:
        cfg = yaml.safe_load(f)
    return cfg["canonical_to_source"]


def load_sku_store_data(
    excel_path: str,
    sheet_name: str | int | None = 0,
    header_row: int = 3,
    data_start_row: int = 4,
    config_dir: str = CONFIG_DIR,
) -> list[SkuStoreRow]:
    """
    Loads a raw SKU-Store Excel extract and maps it to canonical field names.

    Uses pandas + the 'calamine' engine (a fast Rust-based Excel parser) for
    bulk reading — measured ~10x faster than openpyxl's default write/parse
    path at 20,000 rows (largely because openpyxl writes without a shared-
    strings table by default, which bloats the XML and slows re-parsing of
    repeated string values like category/store names). Falls back to
    openpyxl if calamine isn't installed, so this degrades gracefully rather
    than hard-failing.

    Defaults (header_row=3, data_start_row=4) match Sample_RCA_Data.xlsx's
    layout. A different client extract only needs different arguments plus
    an updated column_mapping.yaml — no code changes.
    """
    mapping = load_column_mapping(config_dir)  # canonical -> source
    header_idx = header_row - 1  # pandas header= is 0-indexed

    try:
        df = pd.read_excel(excel_path, sheet_name=sheet_name, header=header_idx, engine="calamine")
    except ImportError:
        df = pd.read_excel(excel_path, sheet_name=sheet_name, header=header_idx, engine="openpyxl")

    df = df.dropna(how="all")
    source_to_canonical = {source: canonical for canonical, source in mapping.items()}
    df = df.rename(columns=source_to_canonical)
    present_canonical_cols = [c for c in mapping.keys() if c in df.columns]
    df = df[present_canonical_cols]

    rows: list[SkuStoreRow] = [SkuStoreRow(rec) for rec in df.to_dict(orient="records")]
    return rows


def load_financial_impact_data(excel_path: str, sheet_name: str = "Financial_Impact_Data") -> dict[tuple[str, str], dict]:
    """
    Loads Financial_Impact_Data.xlsx (unmodified, approved schema) and returns
    a lookup keyed by (SKU_ID, Store_ID) -> {field: value}.
    """
    try:
        df = pd.read_excel(excel_path, sheet_name=sheet_name, engine="calamine")
    except ImportError:
        df = pd.read_excel(excel_path, sheet_name=sheet_name, engine="openpyxl")
    df = df.dropna(how="all")
    lookup: dict[tuple[str, str], dict] = {}
    for record in df.to_dict(orient="records"):
        key = (record["SKU_ID"], record["Store_ID"])
        lookup[key] = record
    return lookup


if __name__ == "__main__":
    # Smoke test
    rows = load_sku_store_data("data/sample/Sample_RCA_Data.xlsx")
    print(f"Loaded {len(rows)} SKU-Store rows")
    print("Sample row 0:", rows[0].fields.get("SKU_ID"), rows[0].fields.get("S01_Weeks_Cover"))

    fin = load_financial_impact_data("data/sample/Financial_Impact_Data.xlsx")
    print(f"Loaded {len(fin)} financial records")
    k = next(iter(fin))
    print("Sample financial record:", k, fin[k])

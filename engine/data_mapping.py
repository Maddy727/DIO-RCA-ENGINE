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
    sheet_name: str | None = None,
    header_row: int = 3,
    data_start_row: int = 4,
    config_dir: str = CONFIG_DIR,
) -> list[SkuStoreRow]:
    """
    Loads a raw SKU-Store Excel extract and maps it to canonical field names.

    Defaults (sheet_name=None -> active sheet, header_row=3, data_start_row=4)
    match Sample_RCA_Data.xlsx's layout. A different client extract only
    needs different header_row/data_start_row/sheet_name arguments plus an
    updated column_mapping.yaml — no code changes.
    """
    mapping = load_column_mapping(config_dir)  # canonical -> source
    wb = openpyxl.load_workbook(excel_path, data_only=True)
    ws = wb[sheet_name] if sheet_name else wb.active

    source_headers = [c.value for c in ws[header_row]]
    source_col_index = {h: i for i, h in enumerate(source_headers) if h is not None}

    rows: list[SkuStoreRow] = []
    for r in range(data_start_row, ws.max_row + 1):
        raw = [ws.cell(row=r, column=i + 1).value for i in range(len(source_headers))]
        if all(v is None for v in raw):
            continue
        canonical_row = {}
        for canonical_name, source_name in mapping.items():
            idx = source_col_index.get(source_name)
            canonical_row[canonical_name] = raw[idx] if idx is not None else None
        rows.append(SkuStoreRow(canonical_row))

    return rows


def load_financial_impact_data(excel_path: str, sheet_name: str = "Financial_Impact_Data") -> dict[tuple[str, str], dict]:
    """
    Loads Financial_Impact_Data.xlsx (unmodified, approved schema) and returns
    a lookup keyed by (SKU_ID, Store_ID) -> {field: value}.
    """
    wb = openpyxl.load_workbook(excel_path, data_only=True)
    ws = wb[sheet_name]
    headers = [c.value for c in ws[1]]
    lookup: dict[tuple[str, str], dict] = {}
    for r in range(2, ws.max_row + 1):
        row = [ws.cell(row=r, column=i + 1).value for i in range(len(headers))]
        if all(v is None for v in row):
            continue
        record = dict(zip(headers, row))
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

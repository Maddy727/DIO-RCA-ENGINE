# DIO RCA Engine

A deterministic, rule-based Root Cause Analysis engine for high Days
Inventory Outstanding (DIO) situations at the SKU-Store level, built
directly from 6 approved Excel business-logic files. No LLM/AI attribution,
no hard-coded thresholds in Python, no Streamlit yet (per instruction).

## Validation status

- **RCA Engine: 70/70 sample rows match ground truth exactly** (`tests/test_rca_engine.py`)
- **Store Action: all spot-checks pass** — no ground-truth column exists for this module, so validation is representative-row + structural (`tests/test_store_action.py`)
- **Corrective Action: row counts match exactly, no root cause left unmapped** (`tests/test_corrective_action.py`)
- **Priority: percentile logic validated with synthetic multi-SKU-per-store data**, because the real 70-row sample has exactly one SKU per store and can only exercise the small-population fallback (`tests/test_priority.py`)

Run all tests: `for f in tests/test_*.py; do python3 "$f"; done`
Run the full pipeline: `python3 engine/orchestrator.py`

## Architecture

```
config/            -- 6 YAML files, one per Excel source, pure transcription
  rca_rules.yaml
  kpi_parameters.yaml
  store_action_rules.yaml
  corrective_action_map.yaml
  priority_logic.yaml
  column_mapping.yaml

engine/
  data_mapping.py       -- Layer 1: raw Excel -> canonical schema
  rca_engine.py          -- Layer 3: 19-rule deterministic RCA
  problem_area.py        -- Layer 4: root cause -> Demand/Supply/Network/Others
  store_action.py        -- Layer 5: sequential decision-support cascade
  corrective_action.py   -- Layer 6: root cause -> corrective action/owner
  priority.py             -- Layer 7: 4 sub-scores -> weighted priority score
  orchestrator.py         -- wires all 4 modules, writes 4 independent outputs

tests/               -- one file per module, run independently before integration
data/sample/          -- the 8 approved Excel files (untouched)
data/outputs/          -- generated CSV outputs (rca/store_action/corrective_action/priority)
ml_future/            -- empty placeholder, not implemented
streamlit_app/         -- empty placeholder, out of scope per instruction
```

Every business-logic file maps 1:1 to a config file and an engine module.
Changing a threshold means re-running `externalize_configs.py` after
editing the Excel file — never touching Python.

## Business logic implemented (traceable to source)

- **Rule 1 gate**: `S01_Weeks_Cover <= 1.1 * Target` -> "No Action Required"
- **Rules 2-13, 17-19**: independent, may co-fire (multiple simultaneous root causes, per Principle #6/#7)
- **Rules 14/15/16** (perishable expiry): mutually exclusive, strict order, **run independently of the Rule-1 gate** (Gap 4 — confirmed: expired/near-expiry stock always surfaces regardless of Weeks Cover)
- **Active Promo suppression** (Gap 2): Rule 3 firing suppresses Rules 8, 9, 11, 12, 17, 18 (all "excess"-type causes) UNLESS `S01_Weeks_Cover > 3 * Target` — confirmed via sample Row 4
- **Day/week unit conversion** (Gap 1): Rules 6 and 15, and the equivalent Store_Action.xlsx steps, all use `S01_Weeks_Cover * 7` consistently — confirmed fully resolved and verified in the corrected `Store_Action.xlsx`
- **Store Action** (Gap 3): a single sequential cascade per SKU-Store, intentionally NOT branched per RCA root cause — confirmed design, not redesigned
- **Priority eligibility**: "DIO intervention population" = gate open OR a perishable expiry rule fired independently of the gate (derived directly from RCA output, not a new rule)
- **Margin / Excess Value percentiles**: calculated **within Store_ID**, eligible population only; stores with < 4 eligible rows get a fixed score of 3 with NULL percentile fields (no network-wide fallback, no raw rank)

## Two technical (non-business-logic) issues found and handled during implementation

1. **Case-sensitivity mismatch** between `RCA_Rules.xlsx` and the Corrective
   Action mapping file for 3 root causes ("high forecast bias" vs "High
   Forecast Bias", "high stock vs peers" vs "High stock vs peers", "High
   Stock vs Format" vs "high stock vs format"). Handled with a
   case-insensitive join key in `problem_area.py` and `corrective_action.py`
   — the RCA engine's original casing is still what's written to output;
   only the *lookup* ignores case. This is a data-entry inconsistency in
   the source files, not a business-rule change — worth a cosmetic fix in
   the Excel files at your convenience, but not blocking.

2. **The 70-row sample cannot test the Priority module's percentile branch**
   at all, because every store has exactly 1 SKU (population always < 4,
   fallback always applies). I built a separate synthetic test
   (`tests/test_priority.py`) to validate the percentile logic — including
   an explicit check that scoring is within-store and not network-wide —
   since the real sample gives false confidence here (100% test pass rate
   on the sample would look the same whether the percentile logic was
   right or completely broken).

## Two flagged assumptions in priority.py (not silently decided — see module docstring)

- **Urgency Score**: if a row is neither perishable-relevant nor seasonal
  (both `S22_Shelf_Life_Remaining_Days` and `S09_Days_To_Season_End` are
  unavailable/sentinel), there's no `MIN()` to score against
  `Priority_Logic.xlsx`'s table. Defaulted to the lowest urgency band
  (score = 1), since no imminent deadline exists for that row.
- **DIO Severity Score**: the table only defines bands for ratio >= 1.5x
  Target. A perishable-bypass-eligible row with a DIO ratio below 1.5x
  (e.g. near-zero Weeks Cover on expired stock) doesn't hit any band.
  Defaulted to 0 (no defined severity).

Both are documented in `engine/priority.py`'s module docstring and flagged
here for your review — please confirm or override.

## Streamlit Dashboard (V1)

A 4-persona presentation layer on top of the validated engine outputs.
**Does not run the RCA engine, Store Action, Priority, or any business
logic** — it reads the pre-generated `data/outputs/*.csv` files plus
`Sample_RCA_Data.xlsx` and `Financial_Impact_Data.xlsx`, and presents them.

### Run it

```
python3 engine/orchestrator.py          # regenerate the 4 output CSVs first (they're gitignored)
cd streamlit_app
streamlit run app.py
```

`app.py` (Enterprise Control Tower) is the landing page. `pages/` contains
Regional Manager, Store Manager, and CSCO — Streamlit's built-in page
navigation links them automatically.

### Structure

```
streamlit_app/
├── app.py                       -- Enterprise Control Tower (landing page)
├── pages/
│   ├── 1_Regional_Manager.py
│   ├── 2_Store_Manager.py       -- Daily Task Cards are the primary interface here
│   └── 3_CSCO.py
├── components/
│   ├── kpi_strip.py              -- common DIO|DIO Target|Inv Value|Excess Value strip
│   ├── charts.py                  -- plotly chart builders
│   ├── filters.py                  -- filter panel
│   ├── tables.py                    -- interactive table + row-selection helper
│   ├── drilldown.py                  -- ONE reusable Enterprise->Region->Store->Category->SKU
│   │                                    component, configured per-persona with a level
│   │                                    sequence + entry scope (not 4 separate implementations)
│   ├── sku_detail.py                  -- ONE reusable 4-tab SKU Detail (RCA/Signals/Actions/
│   │                                    Priority), used by every drill-down
│   ├── task_cards.py                   -- Store Manager daily task cards + "For Visibility"
│   │                                     strip for Central-owned root causes
│   └── styling.py                       -- £ formatting, persona colors, CSS
└── utils/
    ├── data_loader.py                    -- loads & joins all 5 sources, Streamlit-cached
    ├── dio_aggregation.py                 -- DIO/Inventory Value/Excess Value methodology
    ├── priority_labels.py                  -- Priority Score normalization + 5-label banding
    └── aggregations.py                      -- root-cause summary, owner/problem-area rollups
```

### Methodology decisions (confirmed with you, documented here for traceability)

**DIO aggregation — value-weighted, not a naive average.** Per SKU-Store,
`Daily_COGS = Unit_Cost × (Current_Stock_Units ÷ DIO_days)` (back-derived
from the same Weeks-Cover-implied sales rate used to build
`Current_Stock_Units` in `Financial_Impact_Data.xlsx` — no new assumption).
Aggregate DIO at any level = `SUM(Inventory_Value) ÷ SUM(Daily_COGS)` — the
standard finance definition of aggregate Days Inventory Outstanding. On the
current sample this gives **35.4 days**, vs. a naive simple average of
**30.7 days** — confirming the weighting materially changes the headline
number. DIO_Target is shown as a value-weighted average (weighted by each
row's Inventory_Value) for direct comparability on the same chart, since a
"Daily COGS at target" concept doesn't exist. Implemented once in
`utils/dio_aggregation.py`, used by every KPI card and ranking table.

**Priority label normalization.** Defined max Priority Score = 5.0 (from
the approved sub-score tables: 0.7×5 + 0.1×5 + 0.1×5 + 0.1×5). Normalized
% = `Priority_Score ÷ 5.0 × 100`, then banded: ≥80% Emergency, ≥60% Urgent,
≥40% High, ≥20% Medium, else Low. Implemented once in
`utils/priority_labels.py`.

**Store Manager task grouping.** Task cards are grouped from the actual,
already-validated `Store_Action_Recommendation` values in
`store_action_output.csv` — not invented labels. Root causes owned by
Demand Planner/Replenishment Planner/Buyer (i.e. `Dashboard_View` doesn't
contain "Store" in the approved Corrective Action mapping) are shown in a
separate "For Visibility — Not Your Action" strip, honestly attributed to
their real owner, rather than as a task the Store Manager is asked to
execute.

**Multiple root causes.** Every list/queue view shows one summary row per
SKU-Store as `"<Root Cause> + N more"` — a presentation-only summary. The
underlying `rca_output.csv` / `corrective_action_output.csv` data, and the
RCA Details tab in SKU Detail, always show every root cause as a separate
row. Nothing is deduplicated or merged in the data itself.

**No fabricated trends.** No historical/weekly dataset exists anywhere in
the 8 source files. The Regional Manager page shows an explicit
"Historical trend requires weekly snapshot data — not available in V1"
placeholder rather than any invented trend numbers.

### Testing

Every page was run headlessly via Streamlit's `AppTest` API (not just
manually eyeballed) with zero exceptions, including: initial render of all
4 pages, a full 3-level drill-down click-path (Region → Store → Category →
SKU) with real data at every depth, a Store Manager task-card button click,
and the SKU Detail component rendering the SKU with the most simultaneous
root causes in the dataset (worst-case stress test for the RCA Details
tab).

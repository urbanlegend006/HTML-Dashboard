# TOSCA Data Integrity Report Dashboard

> Python-generated HTML dashboard for visualising TOSCA data integrity comparison results. Reads a SQLite `.db` file and produces a standalone, portable HTML report with KPIs, charts, interactive matrices, and a full Excel export.

## Features

- **KPI Dashboard** — pass rate, grade, dominant error type, severity counts
- **Charts** — bar, doughnut, and horizontal stacked bar (Chart.js via CDN)
- **Integrity Matrix** — sortable, filterable, searchable table with crosshair hover highlighting (column indigo / row sky blue)
- **Sample Data Explorer** — accordion panels showing up to 5 example records per error type per column
- **Full Excel Report** — client-side button generates a 17-sheet XLSX with all 25,000+ issue records (Summary + 15 error-type sheets + All Issues)
- **Dark Mode** — toggle with persisted preference
- **Collapsible Sidebar** — scroll-spy navigation with tooltips when collapsed
- **Orphaned & Invalid Records** — tabbed viewer with search and pagination
- **Export** — CSV download and clipboard copy with toast notifications
- **Print Styles** — clean print layout hiding sidebar and controls

## Quick Start

### Prerequisites
- Python 3.13+
- A TOSCA-generated SQLite comparison database (named `tosca_report.db` by default)
- Firefox for test runs (Chromium headless shell has ICU issues on Windows)

### Generate the Dashboard

```bash
pip install pytest playwright openpyxl
playwright install firefox

python tosca_di_report_dashboard.py
```

Opens `output/tosca_enterprise_report.html` — a fully self-contained single HTML file. No server needed.

### Run Tests

```bash
python tosca_di_report_dashboard.py    # Regenerate before testing
python -m pytest tests/test_dashboard.py -v --browser firefox
```

23 tests collected — 22 pass. `test_copy_to_clipboard` fails on Firefox (clipboard-read permission unsupported by Playwright). Use `--browser chromium --headed` for clipboard tests.

## Technology Stack

| Layer | Technology |
|---|---|
| Generator | Python 3.13+ (stdlib only: `sqlite3`, `json`, `os`) |
| Frontend | Tailwind CSS + Chart.js (CDN) |
| Excel | SheetJS (CDN) — client-side generation |
| Testing | Pytest + Playwright |

No build step, no server runtime, no external API calls. The HTML loads everything from CDNs at runtime.

## Project Structure

```
tosca_di_report_dashboard.py       # Main generator (single file, ~3100 lines)
tests/test_dashboard.py            # 23 Playwright tests
output/tosca_enterprise_report.html # Generated dashboard
tosca_report.db                    # Input SQLite database
tosca_unified_dashboard_features-v2.md  # Feature reference documentation
opencode.json                      # opencode slash commands
.opencode/skills/tosca-test-gate/  # Development process automation skill
```

### Code Architecture (v4.0)

The generator is organized into focused module-level functions:

| Function | Responsibility |
|---|---|
| `get_meta()` | SQLite metadata value lookup |
| `get_mismatch_type()` | Classifies pairwise diff into 15 error types |
| `build_error_matrix()` | Query Differences table; classify all pairs |
| `extract_unmatched_invalid()` | Fetch unmatched source/target + invalid rows |
| `extract_orphan_counts()` | Read orphan row counts from Metadata |
| `prepare_ui_data()` | Compute KPIs, grade badge, chart data |
| `generate_html()` | Pure HTML template — receives all data via `ctx` dict |
| `generate_unified_dashboard()` | **Orchestrator** — connect → call helpers → build ctx → generate HTML → write file |

## Branch Strategy

All feature work is done on named branches and pushed without merging to `main`. The `main` branch represents the latest stable release state.

## Database Schema

The SQLite database contains:

| Table | Purpose |
|---|---|
| `Metadata` | Report metadata (timestamps, row counts, SQL queries) |
| `Differences` | All compared rows with per-column values (source/target pairs by RowKey) |
| `ColumnNames` | Column ID to column name mapping per table |
| `DifferencesSummary` | Per-column difference counts |
| `UnmatchedSource` / `UnmatchedTarget` | Orphaned rows from each system |
| `InvalidSource` / `InvalidTarget` | Rows that failed comparison preprocessing |
| `Matched` | Rows with no differences |

The 15 error types classified by the dashboard: Source NULL, Target NULL, Null Equivalent Mismatch, Duplicate Value Mismatch, Sorting Issue, Whitespace Mismatch, Case Sensitivity Mismatch, Type Coercion / Formatting, Boolean Format Mismatch, Encoding / Special Char Mismatch, Precision / Rounding, Data Truncation, Date/Timestamp Mismatch, Numeric Data Mismatch, String Data Mismatch.

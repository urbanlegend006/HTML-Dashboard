# TOSCA Data Integrity Report Dashboard â€” Feature & Implementation Reference (v3.1 Enterprise Diagnostics)

> **Purpose:** This document is the single source of truth for the TOSCA DI Report Dashboard project. It captures every implemented feature, architectural decision, and UI/UX specification so that any new team member can onboard immediately without prior context.

---

## Project Overview

The TOSCA DI Report Dashboard is a **single-file Python utility** (`tosca_di_report_dashboard.py`) that reads a TOSCA-generated SQLite comparison database and produces a **standalone, portable HTML dashboard** (`output/tosca_enterprise_report.html`). The dashboard visualises data integrity metrics, mismatch breakdowns, and sample-level error details with a premium, modern UI.

### Technology Stack

| Layer | Technology | Notes |
|---|---|---|
| Backend / Generator | Python 3.13+ (stdlib only) | `sqlite3`, `json`, `os`, `collections.Counter` |
| Frontend Framework | Tailwind CSS (CDN) | Loaded at runtime; customized with Inter font |
| Charting | Chart.js (CDN) | Bar, Doughnut, and Horizontal Stacked Bar charts |
| Testing | Pytest + Playwright | Headless Chromium browser tests |
| Typography | Google Fonts (Inter) | Loaded at runtime for crisp enterprise feel |
| Output | Single HTML file | Fully self-contained; no server needed |

### Folder Structure

```
TOSCA DI Report Dashboard/
â”œâ”€â”€ tosca_di_report_dashboard.py      # Main generator script
â”œâ”€â”€ tosca_unified_dashboard_features-v2.md  # This document
â”œâ”€â”€ *.db                              # Input SQLite databases
â”œâ”€â”€ output/                           # Generated dashboard files
â”‚   â”œâ”€â”€ tosca_enterprise_report.html  # The dashboard
â”‚   â””â”€â”€ tosca_integrity_report.csv   # Exported CSV (user-triggered)
â””â”€â”€ tests/                            # Automated test suite
    â”œâ”€â”€ test_dashboard.py             # Playwright integration tests
    â””â”€â”€ test_output/                  # Playwright download artifacts
```

### Design Scope

- **Desktop-only:** The dashboard is designed exclusively for desktop viewports. No mobile/tablet responsive breakpoints are implemented.
- **Target audience:** QA engineers and system admins reviewing data integrity comparison results.

---

## [x] 1. Data Ingestion & Integrity Sync

- [x] **SQLite3 Direct Parsing:** Connects directly to `.db` files produced by TOSCA's comparison engine.
- [x] **Metadata-Driven KPIs:** Extracts high-level counts (Matched Rows, Processed Rows, Rows with Differences) from `$.reportInfo` keys.
- [x] **Technical-to-Business Mapping:** Resolves internal `ColumnId` integers into business names via the `ColumnNames` table.
- [x] **Output Directory Auto-Creation:** The generator automatically creates the `output/` directory if missing.

---

## [x] 2. Intelligent Mismatch Analytics (Expanded Diagnostics)

- [x] **Multi-Set Sorting Validation:** Sets-based comparison using `collections.Counter` within `RowKey` groups.
- [x] **Pairwise Heuristic Classification (15 Error Types):** Expanded from generic string/numeric mismatch to 15 industry-standard enterprise data quality issues:
    - `Source Value is NULL` & `Target Value is NULL`
    - `Null Equivalent Mismatch` (e.g., 'N/A', 'Unknown')
    - `Duplicate Value Mismatch`
    - `Sorting Issue`
    - `Whitespace Mismatch`
    - `Case Sensitivity Mismatch`
    - `Type Coercion`
    - `Boolean Format`
    - `Encoding / Special Char Mismatch`
    - `Precision / Rounding`
    - `Data Truncation`
    - `Date/Timestamp Mismatch`
    - `Numeric Data Mismatch`
    - `String Data Mismatch`
- [x] **Null-like Match Bypass:** Strict bypassing of functional matches where source is empty string `''` and target is SQLite `NULL`, reducing false positives.
- [x] **Sample Caching:** Stores up to **5 representative samples** per category per column.
- [x] **New Computed Metrics:**
    - **Affected Columns**: Count of columns with any issues.
    - **Critical Fields**: Fields with >1000 total issues.
    - **NULL Issue Rate**: Percentage of NULL-related issues.
    - **Dominant Error**: Most frequent error type across all columns.

---

## [x] 3. UI/UX â€” Premium Layout & Navigation

The dashboard uses a modern **Sidebar + Main Content** web-app layout with enhanced interactivity.

# TOSCA Data Integrity Report Dashboard â€” Feature & Implementation Reference (v3.1 Enterprise Diagnostics)

> **Purpose:** This document is the single source of truth for the TOSCA DI Report Dashboard project. It captures every implemented feature, architectural decision, and UI/UX specification so that any new team member can onboard immediately without prior context.

---

## Project Overview

The TOSCA DI Report Dashboard is a **single-file Python utility** (`tosca_di_report_dashboard.py`) that reads a TOSCA-generated SQLite comparison database and produces a **standalone, portable HTML dashboard** (`output/tosca_enterprise_report.html`). The dashboard visualises data integrity metrics, mismatch breakdowns, and sample-level error details with a premium, modern UI.

### Technology Stack

| Layer | Technology | Notes |
|---|---|---|
| Backend / Generator | Python 3.13+ (stdlib only) | `sqlite3`, `json`, `os`, `collections.Counter` |
| Frontend Framework | Tailwind CSS (CDN) | Loaded at runtime; customized with Inter font |
| Charting | Chart.js (CDN) | Bar, Doughnut, and Horizontal Stacked Bar charts |
| Testing | Pytest + Playwright | Headless Chromium browser tests |
| Typography | Google Fonts (Inter) | Loaded at runtime for crisp enterprise feel |
| Output | Single HTML file | Fully self-contained; no server needed |

### Folder Structure

```
TOSCA DI Report Dashboard/
â”œâ”€â”€ tosca_di_report_dashboard.py      # Main generator script
â”œâ”€â”€ tosca_unified_dashboard_features-v2.md  # This document
â”œâ”€â”€ *.db                              # Input SQLite databases
â”œâ”€â”€ output/                           # Generated dashboard files
â”‚   â”œâ”€â”€ tosca_enterprise_report.html  # The dashboard
â”‚   â””â”€â”€ tosca_integrity_report.csv   # Exported CSV (user-triggered)
â””â”€â”€ tests/                            # Automated test suite
    â”œâ”€â”€ test_dashboard.py             # Playwright integration tests
    â””â”€â”€ test_output/                  # Playwright download artifacts
```

### Design Scope

- **Desktop-only:** The dashboard is designed exclusively for desktop viewports. No mobile/tablet responsive breakpoints are implemented.
- **Target audience:** QA engineers and system admins reviewing data integrity comparison results.

---

## [x] 1. Data Ingestion & Integrity Sync

- [x] **SQLite3 Direct Parsing:** Connects directly to `.db` files produced by TOSCA's comparison engine.
- [x] **Metadata-Driven KPIs:** Extracts high-level counts (Matched Rows, Processed Rows, Rows with Differences) from `$.reportInfo` keys.
- [x] **Technical-to-Business Mapping:** Resolves internal `ColumnId` integers into business names via the `ColumnNames` table.
- [x] **Output Directory Auto-Creation:** The generator automatically creates the `output/` directory if missing.

---

## [x] 2. Intelligent Mismatch Analytics (Expanded Diagnostics)

- [x] **Multi-Set Sorting Validation:** Sets-based comparison using `collections.Counter` within `RowKey` groups.
- [x] **Pairwise Heuristic Classification (15 Error Types):** Expanded from generic string/numeric mismatch to 15 industry-standard enterprise data quality issues:
    - `Source Value is NULL` & `Target Value is NULL`
    - `Null Equivalent Mismatch` (e.g., 'N/A', 'Unknown')
    - `Duplicate Value Mismatch`
    - `Sorting Issue`
    - `Whitespace Mismatch`
    - `Case Sensitivity Mismatch`
    - `Type Coercion`
    - `Boolean Format`
    - `Encoding / Special Char Mismatch`
    - `Precision / Rounding`
    - `Data Truncation`
    - `Date/Timestamp Mismatch`
    - `Numeric Data Mismatch`
    - `String Data Mismatch`
- [x] **Null-like Match Bypass:** Strict bypassing of functional matches where source is empty string `''` and target is SQLite `NULL`, reducing false positives.
- [x] **Sample Caching:** Stores up to **5 representative samples** per category per column.
- [x] **New Computed Metrics:**
    - **Affected Columns**: Count of columns with any issues.
    - **Critical Fields**: Fields with >1000 total issues.
    - **NULL Issue Rate**: Percentage of NULL-related issues.
    - **Dominant Error**: Most frequent error type across all columns.

---

## [x] 3. UI/UX â€” Premium Layout & Navigation

The dashboard uses a modern **Sidebar + Main Content** web-app layout with enhanced interactivity.

### Collapsible Mini-Sidebar (v2.2)

The sidebar supports two states â€” **Expanded** (full width) and **Collapsed** (icon rail) â€” with smooth CSS transitions.

- [x] **Expanded State (default, `width: 16rem`):**
    - Shows the "T" logo + "TOSCA DI" branding text.
    - Navigation links display both SVG icon and text label.
    - **Sidebar order (v3.3):** Overview → Analytics → Integrity Matrix → Test Queries.
    - User profile block shows "QA" avatar badge + "System Admin / View Only" text.
    - A small **left-pointing arrow** (`‹`) toggle button sits right-aligned just above the nav links.
- [x] **Collapsed State (`width: 4.5rem`):**
    - Only the "T" logo (no text), nav **icons only** (centered), and the "QA" badge (no text) are shown.
    - The toggle arrow flips to **point right** (`›`) indicating "expand".
    - Text labels fade out via `opacity: 0` + `max-width: 0` CSS transitions.
- [x] **State Persistence:** Sidebar collapsed/expanded state is stored in `localStorage.sidebarCollapsed`.
- [x] **Arrow Direction Logic:** Controlled via JavaScript â€” the SVG `<path>` `d` attribute is swapped between `M15 19l-7-7 7-7` (left) and `M9 5l7 7-7 7` (right) on toggle.

### Other Layout Features

- [x] **Scroll-Spy Highlighting:** Nav links automatically highlight based on the current scroll position. The `sections` array must match the DOM order — `['kpi-section', 'charts', 'matrix', 'test-queries']` — otherwise later sections override earlier ones when scrolled into view (v3.4 bugfix).
- [x] **Sticky Top Header:**
    - Displays title, database name (truncated for space with a â“˜ hover tooltip revealing the full DSN), and execution date.
    - **Glassmorphism:** Uses `backdrop-blur-md` for a frosted-glass effect.
    - **Dynamic Grade Badge (v3.0):** Animated pulsing visual indicator of report grade (A+, A, B, C, D) based on overall pass rate.
- [x] **Scroll-to-Top FAB:** A floating action button appears after scrolling down 300px for quick return to top.
- [x] **Main Content Capping:** Capped at `max-w-[1400px]` for optimal readability.

---

## [x] 4. UI/UX â€” Visual Design System

- [x] **Typography:** Loads **Inter** font from Google Fonts for a professional enterprise look.
- [x] **Color Palette:** Refined Indigo/Slate palette with CSS Custom Properties (`--surface`, `--accent`, etc.) for consistent theming.
- [x] **Light Mode is the Default:** The dashboard opens in light mode when no saved preference exists. Only if `localStorage.theme` is explicitly set to `'dark'` will dark mode be applied on load.
- [x] **High-Contrast Dark Mode (v3.3):** Switched to a GitHub-dark-inspired palette: body `#0d1117`, panels/sidebar `#161b22`, card surfaces `#1c2333`-equivalent, borders `#30363d`. All secondary text upgraded from `slate-400` to `slate-300` for sharper legibility. Tab backgrounds, glass borders, and scrollbars all updated for high contrast.
- [x] **Premium Glassmorphism:** Cards use subtle semi-transparent backgrounds with blur and thin high-contrast borders.
- [x] **Accent Hover Borders:** All major tile containers (KPI cards, Doughnut chart, Bar chart, Integrity Matrix) transition to an `indigo-500/50` border on hover for visual focus.

### Theme Initialization Logic

```javascript
// Light is the default - only switch to dark if explicitly stored
if (localStorage.theme === 'dark') {
    htmlClass.add('dark');
} else {
    htmlClass.remove('dark');
}
```

---

## [x] 5. UI/UX â€” Dynamic Components

- [x] **Animated KPI Counters:** Numbers animate from 0 to target value on page load with a 1.5s ease-out effect.
- [x] **KPI Card Shimmer:** Subtle inner gradient shimmer on card hover.
- [x] **Animated Accordions:** Matrix rows expand with a smooth `slideDown` animation (max-height transition) instead of an instant toggle.
- [x] **Hover Micro-Animations:** SVG icons rotate or translate slightly on button/toggle hover.
- [x] **Staggered Entrance Animation (v3.0):** KPI cards fade in and slide up sequentially (100ms delay between each) on page load.
- [x] **Toast Notifications (v3.0):** Replaces inline feedback text. Floating alerts appear at the bottom center and slide out automatically after a brief timeout.

---

## [x] 6. UI/UX â€” Data Visualisations

### KPI Cards (v3.0)
Expanded to 8 metrics across two rows under the **Summary and KPIs** section title:
- **Row 1:** Total Source Rows, Identical Matches, Rows with Diffs, Overall Pass Rate
- **Row 2:** Affected Columns, Critical Fields, NULL Issue Rate, Dominant Error

### Tabbed Analytics Panel (v3.0)
The charts section uses a visibly clickable, bordered tab container for organized insights:
- **Tab 1: Overview Charts** (Integrity Health Score Doughnut & Top 5 Affected Columns Bar Chart)
  - **Bar Chart Click-to-Filter (v3.3):** Clicking a bar in the Top Affected Columns chart automatically populates the Integrity Matrix search field and scrolls to the matching row.
- **Tab 2: Error Distribution** (Horizontal stacked bar chart showing error types broken down by column, complete with interactive 15-item legend)
- **Tab 3: Orphaned Records (v3.3):** Shows orphaned rows from source/target datasets.
  - **Two summary tiles:** Source Orphans (rows in target not found in source) and Target Orphans (rows in source not found in target) in a 2-column grid.
  - Invalid Source and Invalid Target tiles were **removed** in v3.3 to reduce clutter.
  - Searchable, paginated table with dynamic column rendering and empty-state messaging.

### Test Queries Section

- [x] **Sidebar Navigation:** Test Queries is a first-class sidebar destination and scroll-spy section (`#test-queries`). It is the **last item** in the sidebar (v3.3: moved from position 3 to position 4, after Integrity Matrix).
- [x] **Source/Target Query Details:** Displays source and target SQL queries fetched from the DB metadata, along with their Connection String/DSN, styled with DB icons and one-click copy-to-clipboard buttons.
- [x] **Theme-Aware SQL Blocks:** SQL query panels use a soft slate-gray background in light mode and a higher-contrast dark slate background in dark mode.
- [x] **Readable Query Typography:** SQL and DSN code panels use 13px monospace text with roomier line height, stronger foreground contrast, and clearer light/dark borders.
### Integrity Health Score (Doughnut Chart)

- [x] **Doughnut Chart:** Visual match/diff ratio in the center.
- [x] **Enlarged Canvas:** Sized at `w-64 h-64` so the percentage text doesn't crowd the arc. 
- [x] **Health Indicators:** Color-coded dots for Matched, Differences, and Missing/Other.
- [x] **Central Metric:** Overall match percentage prominently displayed in the doughnut hole.

### Top Affected Columns (Gradient Bar Chart)

- [x] **Gradient Bars:** Horizontal indigo-to-violet linear gradients (`indexAxis: 'y'`) replace flat solid vertical colors for better label readability.
- [x] **Rounded Bars:** `borderRadius: 8` for a modern, soft aesthetic.

### Error Distribution Chart
- **Horizontal Stacked Bar Chart:** Expansive color map separating all 15 error types. Lazy-initialized on tab click.

### Chart Tooltips (High Contrast Fix)

Charts use **theme-aware tooltips** that adapt their background/text colors to the active theme.

```javascript
// Tooltip colors are set per theme and applied on theme toggle
const tooltipBg    = isDark ? '#1e293b' : '#ffffff';
const tooltipTitle = isDark ? '#ffffff' : '#0f172a';
const tooltipBody  = isDark ? '#cbd5e1' : '#475569';

// Applied to all charts:
chart.options.plugins.tooltip.backgroundColor = tooltipBg;
chart.options.plugins.tooltip.titleColor      = tooltipTitle;
chart.options.plugins.tooltip.bodyColor       = tooltipBody;
```

---

## [x] 7. Integrity Matrix â€” Error Detail Table

### Table Polish

- [x] **Sticky Header & Footer:** The table header remains visible at the top, and a new sticky summary footer (`<tfoot>`) displays global column totals at the bottom.
- [x] **Matrix Readability Refresh (v3.2):** Matrix headers and footers use 10px labels, body cells remain at readable `text-xs`, and zero-value cells use muted but visible slate text instead of near-invisible pale text.
- [x] **Detailed Tooltips:** Each error column header (e.g., Src NULL, Dupe, Total, % Total) features a styled CSS-only dropdown tooltip explaining exactly what the data integrity issue means.
- [x] **JS Zebra Striping:** Dynamic alternating row colors that persist after sorting or filtering.
- [x] **Row Count Badge:** Shows the total number of fields in the matrix header.
- [x] **Center Alignment:** Numeric columns remain center-aligned as per user preference for visual balance.
- [x] **Percentage Column:** Added a `% Total` column to immediately identify heavily affected fields.
- [x] **Clean Empty Cells:** Both database `NULL` values and empty strings `''` are unified and render as completely blank cells in the Sample Explorer for a clean, Excel-like grid layout.

### Dynamic Row-Key Columns
- [x] **Configurable Keys:** Row-Key columns are passed dynamically as a Python list (`row_keys = [...]`) ensuring the dashboard adapts to any dataset structure.
- [x] **Badge Chips:** In the sample explorer, pipe-delimited composite keys are beautifully split into colored, monospace badge chips instead of raw text.
- [x] **Info Strip:** A compact info strip below the matrix header displays the detected/provided key columns using key icons, providing instant context.

### Row Severity Colors & Filtering (v3.0)

In **Light Mode**, severity-based row background colors are highly saturated. In **Dark Mode**, they use subtle tints.

| Severity | Light Mode Background | Dark Mode Background | Condition |
|---|---|---|---|
| Critical | `bg-red-100/60` â†’ `bg-red-100/80` (hover) | `bg-red-900/10` | >1000 Total Issues |
| Warning | `bg-yellow-100/60` â†’ `bg-yellow-100/80` (hover) | `bg-yellow-900/10` | 101â€“1000 Total Issues |
| Info | `bg-white/50` â†’ `bg-slate-100` (hover) | `bg-[#0f172a]/50` | â‰¤100 Total Issues |

- [x] **Severity Filter Buttons (v3.0):** Filter the matrix using quick toggles (All, Critical, Warning, Info) with exact counts displayed inline.

### Search, Sorting & Expand Controls

- [x] **Live Search:** Filters rows in real-time; automatically refreshes zebra striping. Search term is also factored into the unified `applyMatrixFilters()` logic alongside severity and type filters.
- [x] **Multi-Type Sorting:** Alphabetical for fields, numeric for counts.
- [x] **Expand All / Collapse All (v3.0):** Instantly expand or collapse all visible Sample Data Explorer accordions at once.
- [x] **Mismatch Type Dropdown (v3.3):** Dropdown above the matrix to filter rows matching a specific mismatch category (e.g., Whitespace Mismatch, Null Equivalent Mismatch).
- [x] **Active Filters Badge (v3.3):** A live badge above the matrix shows the current active filters (search term, severity, mismatch type) with a one-click reset button.
- [x] **Crosshair Hover Highlighting (v3.4):** Hovering over a matrix data cell highlights both the column (vertical) and row (horizontal) simultaneously, creating a true crosshair effect. Column uses indigo-100/50 shades, row uses amber-50/60 shades for clear visual distinction. Dark mode uses subtle 5-10% opacity tints. Highlights are removed when leaving the table entirely (no flicker between cell-to-cell moves).

---

## [x] 8. Export & Clipboard Utilities

- [x] **Export CSV:** Generates `tosca_integrity_report_[timestamp].csv` with Excel-compatible UTF-8 BOM. Features a timestamped filename and success toast notification.
- [x] **Copy to Clipboard:** Copies tab-separated data of visible rows (including `% Total`). Features a success toast notification.
- [x] **Copy SQL Queries:** Dedicated copy buttons for both Source and Target queries in the standalone Test Queries section.

---

## [x] 9. Automated Test Suite

Located in `tests/test_dashboard.py`. Uses **Pytest + Playwright**.

| Test Case | What It Validates |
|---|---|
| `test_dashboard_loads_correctly` | Page title, h1 heading, KPI card visibility |
| `test_dark_mode_toggle` | Theme toggle flips the root HTML class |
| `test_matrix_search_filtering` | Live search filters rows correctly |
| `test_accordion_expansion` | Row click expands panel (validates visibility + sample text) |
| `test_table_sorting` | Sorting logic reorders rows correctly |
| `test_copy_to_clipboard` | Clipboard population and verifies toast notification |
| `test_csv_export` | CSV download with updated filename |
| `test_readability_style_contract` | Font sizes, zero-value text color, dark mode background contract |
| `test_orphans_tab_interaction` | Tab switching, search, empty-state, card click for orphaned records |
| `test_mismatch_type_dropdown_filter` | Dropdown filter shows/hides rows; active badge appears and resets |
| `test_bar_chart_click_filters_matrix` | Bar click sets search value and shows active filter badge |
| `test_sidebar_nav_active` | Verifies all 4 sidebar nav links get `nav-active` class when clicked, including Test Queries |
| `test_crosshair_column_highlight` | Hovering a matrix cell highlights its column with indigo classes |
| `test_crosshair_row_highlight` | Hovering a matrix cell highlights its row with amber classes |
| `test_crosshair_clears_on_mouseleave` | Crosshair classes are removed when mouse leaves the table |

**Running tests:**

```bash
# Regenerate the report first
python tosca_di_report_dashboard.py

# Run all 15 tests (use Firefox if Chromium headless shell has ICU issues on Windows)
python -m pytest tests/test_dashboard.py -v --browser firefox

# Or run with Chromium in headed mode for clipboard tests
python -m pytest tests/test_dashboard.py -v --browser chromium --headed
```

---

## Quick Start for New Developers

1. **Prerequisites:** Python 3.13+, `pip install pytest playwright`, `playwright install chromium`.
2. **Generate the dashboard:**
   ```bash
   python tosca_di_report_dashboard.py
   ```
   This reads the `.db` file and writes `output/tosca_enterprise_report.html`.
3. **View the dashboard:** Open `output/tosca_enterprise_report.html` in any modern browser or host locally using a python server (`python -m http.server 8080 --directory output`).
4. **Run tests:**
   ```bash
   python -m pytest tests/test_dashboard.py -v --browser firefox
   ```
   All 15 tests should pass. 1 pre-existing failure in `test_copy_to_clipboard` when using Firefox (clipboard-read permission unsupported). Use `--browser chromium --headed` if Chromium headless shell has ICU data issues on your Windows machine.
5. **Key design decisions:**
   - **Light mode is the default.** Dark mode is only used if the user explicitly toggles it or has a saved `localStorage.theme = 'dark'` preference.
   - **Desktop only.** No mobile/tablet breakpoints.
   - **Numeric columns are center-aligned** in the Integrity Matrix.
   - **Sidebar state persists** in `localStorage` across sessions.

---

## Changelog

| Date | Version | Change | Details |
|---|---|---|---|
| 2026-05-21 | **v3.4 Scroll-Spy Bugfix & Crosshair** | Scroll-spy fix, Orphaned tab rename, crosshair hover, sidebar nav test | Fixed scroll-spy `sections` array order so Test Queries nav link gets `nav-active` styling. Renamed "Orphaned & Invalid Records" to "Orphaned Records". Replaced column-only hover with full crosshair (row + column) highlighting — column uses indigo, row uses amber for clear visual distinction. Fixed light mode hover colors (indigo-500/10 → indigo-100). Added `test_sidebar_nav_active`. Expanded test suite from 11 to 12 Playwright tests. |
| 2026-05-21 | **v3.3 Interactivity & UX Polish** | Sidebar reorder, Orphaned tab trim, Dark mode rework, Chart/Matrix filters | Moved Test Queries to last sidebar position. Removed Invalid Source/Target tiles from Orphaned tab (now 2-tile grid: Source Orphans, Target Orphans). Overhauled dark mode to GitHub-dark palette (#0d1117/#161b22). Added bar chart click-to-filter matrix, Mismatch Type dropdown, Active Filters badge, column hover highlighting. Expanded test suite from 7 to 11 Playwright tests. |
| 2026-05-21 | **v3.2 Navigation & Readability Refresh** | Sidebar Test Queries, Light Default, KPI Title, Readability | Moved Test Queries from the Analytics tab set into a standalone sidebar destination. Added the Summary and KPIs heading above the eight KPI tiles. Restyled Analytics tabs with visible backgrounds and borders. Changed first-load theme behavior to light mode by default while preserving dark-mode toggle persistence. Lightened dark-mode surfaces, improved low-contrast labels, increased matrix/code typography, and updated SQL/DSN panels with theme-aware slate backgrounds. |
| 2026-05-18 | **v3.1 Enterprise Diagnostics** | 15-Issue Expansion, Test Queries Tab, UI Polish | Overhauled data integrity checks to detect 15 industry-standard errors. Added Tab 3 for SQL Test Queries. Converted bar chart to horizontal. Fixed Matrix Total filtering. Replaced 'None' with clean empty cells. Transformed row keys into colored badge chips and added dynamic `row_keys` list parameter. Added detailed CSS dropdown tooltips to matrix headers. Added sticky footer for column totals. |
| 2026-05-02 | **v3.0 Enterprise** | Comprehensive Modernization | Added dynamic Grade Badge with pulse animation. Expanded KPIs to 2 rows (8 metrics total) with staggered entrance animations. Converted Analytics to a tabbed UI, introducing an Error Distribution horizontal stacked bar chart. Added severity filter buttons and expand/collapse all controls to Integrity Matrix. Replaced inline feedback with a floating toast notification system. |
| 2026-05-01 | **v2.2 Refined** | Collapsible mini-sidebar, doughnut enlargement, accent borders, tooltip fixes, light-mode table saturation | Sidebar collapses to icon-only rail (4.5rem) with directional arrow toggle. Doughnut canvas enlarged to w-64/h-64. Accent hover borders on all tiles. High-contrast theme-aware tooltips on both charts. Increased light-mode row color saturation. Removed faded exclamation decoration. Default dark mode enforced. |
| 2026-05-01 | v2.1 Premium | Inter font, animated counters, glassmorphism, doughnut chart, sticky headers, zebra striping | Full visual overhaul with premium design tokens, animated KPIs, scroll-spy nav, and FAB. |
| 2026-04-26 | v2.0 | Sidebar Overhaul | Sidebar layout, indigo/slate palette, dark mode, CSV/Clipboard, Playwright tests. |
| 2026-04-26 | v1.0 | Initial Dashboard | Core data pipeline, KPIs, bar chart, error matrix with accordion. |

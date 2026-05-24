# TOSCA Dashboard UI/UX Automated Test Report

**Execution Engine**: `pytest-playwright` (Chromium)
**Test Target**: `tosca_enterprise_report.html`
**Result**: 100% Passed (7/7) 🟢

## Test Case Breakdown

| Test Case | Description | Status |
| :--- | :--- | :---: |
| `test_dashboard_loads_correctly` | Verifies that the dashboard renders the main containers, correct title, and primary KPI elements are visible in the DOM. | ✅ |
| `test_dark_mode_toggle` | Verifies that clicking the `🌓` theme toggle successfully modifies the root HTML class to swap the active color palette. | ✅ |
| `test_matrix_search_filtering` | Validates the live search box. Asserts that filtering for `PARAMETER_MAPPING_ID` restricts the matrix view correctly and restores rows when cleared. | ✅ |
| `test_accordion_expansion` | Checks that clicking on a hidden `Sample Data Explorer` matrix row correctly modifies its DOM state to `visible`. | ✅ |
| `test_table_sorting` | Simulates user clicks on the "Total Issues" column header and verifies that the `data-val` attributes flip direction correctly from Descending to Ascending. | ✅ |
| `test_copy_to_clipboard` | Verifies that the new "Copy List" button properly extracts visible row data, modifies the clipboard, and triggers the "Copied!" feedback text. | ✅ |
| `test_csv_export` | Intercepts the browser download event triggered by "Export CSV" to verify that a file named `error_matrix_summary.csv` is correctly prepared for download. | ✅ |

> [!TIP]
> The automated test script (`test_dashboard.py`) has been left in your project directory. You can rerun it anytime to guard against regressions using:
> `pytest test_dashboard.py -v`

import os
import pytest
from playwright.sync_api import Page, expect
import time
import math

@pytest.fixture(scope="session")
def dashboard_url():
    # Use absolute file path for the dashboard
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    html_file = os.path.join(project_root, "output", "tosca_enterprise_report.html")
    # Regenerate the HTML just in case
    import sys
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    import tosca_di_report_dashboard
    tosca_di_report_dashboard.generate_unified_dashboard(
        "tosca_report.db", 
        html_file
    )
    return f"file:///{html_file.replace(chr(92), '/')}"

def test_dashboard_loads_correctly(page: Page, dashboard_url: str):
    page.goto(dashboard_url)
    expect(page).to_have_title("TOSCA Enterprise Integrity")
    expect(page.locator("h1").first).to_contain_text("Dashboard Overview")
    # Check KPIs
    expect(page.locator("text=Total Source Rows")).to_be_visible()
    expect(page.locator("text=Identical Matches")).to_be_visible()
    
def test_dark_mode_toggle(page: Page, dashboard_url: str):
    page.goto(dashboard_url)
    page.evaluate("localStorage.removeItem('theme')")
    page.reload()
    html = page.locator("html")
    
    # Light mode is the default when no saved preference exists.
    initial_class = html.get_attribute("class") or ""
    assert "dark" not in initial_class
    
    # Click toggle to dark mode.
    page.locator("#themeToggle").click()
    dark_class = html.get_attribute("class") or ""
    assert "dark" in dark_class

    # Toggle back to light mode.
    page.locator("#themeToggle").click()
    light_class = html.get_attribute("class") or ""
    assert "dark" not in light_class
    
def test_matrix_search_filtering(page: Page, dashboard_url: str):
    page.goto(dashboard_url)
    
    # Count rows before filter
    initial_rows = page.locator(".matrix-row:visible").count()
    assert initial_rows > 0
    
    # Filter for a specific column
    search_input = page.locator("#matrixSearch")
    search_input.fill("PARAMETER_MAPPING_ID")
    
    # There should be exactly 1 visible matrix row
    visible_rows = page.locator(".matrix-row:visible").count()
    assert visible_rows == 1
    
    # Clear filter
    search_input.fill("")
    assert page.locator(".matrix-row:visible").count() == initial_rows

def test_accordion_expansion(page: Page, dashboard_url: str):
    page.goto(dashboard_url)
    
    # Find the first row
    first_row = page.locator(".matrix-row").first
    row_id_match = first_row.get_attribute("onclick")
    acc_id = row_id_match.split("'")[1]
    
    acc_row = page.locator(f"#{acc_id}")
    
    # Initially hidden
    expect(acc_row).to_be_hidden()
    
    # Click to expand
    first_row.click()
    
    # Now it should be visible
    expect(acc_row).to_be_visible()
    expect(acc_row.locator("text=Sample Data Explorer")).to_be_visible()

def test_table_sorting(page: Page, dashboard_url: str):
    page.goto(dashboard_url)
    
    # Get first row's data-val before sort (Total column is second to last)
    first_row_val_before = page.locator(".matrix-row").first.locator("td:nth-last-child(2)").get_attribute("data-val")
    
    # Click "Total" column twice to sort ascending
    page.locator("th:has-text('Total Issues')").click()
    page.locator("th:has-text('Total Issues')").click()
    
    # Get first row's data-val after sort
    first_row_val_after = page.locator(".matrix-row").first.locator("td:nth-last-child(2)").get_attribute("data-val")
    
    assert first_row_val_before != first_row_val_after

def test_copy_to_clipboard(page: Page, dashboard_url: str):
    # Need to grant clipboard permissions
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    page.goto(dashboard_url)
    
    page.locator("#copyBtn").click()
    
    # v3.0: Verify toast notification appears instead of inline text
    toast = page.locator("#toast-notification")
    expect(toast).to_be_visible()
    expect(toast).to_contain_text("Matrix data copied to clipboard")
    
    # Verify clipboard content
    clipboard_text = page.evaluate("navigator.clipboard.readText()")
    assert "Field\tSource Value is NULL\tTarget Value is NULL\tNull Equivalent Mismatch" in clipboard_text
    assert "PARAMETER_MAPPING_ID" in clipboard_text

def test_csv_export(page: Page, dashboard_url: str):
    page.goto(dashboard_url)
    
    with page.expect_download() as download_info:
        page.locator("text=Export CSV").click()
        
    download = download_info.value
    assert download.suggested_filename.startswith("tosca_integrity_report") and download.suggested_filename.endswith(".csv")

def test_readability_style_contract(page: Page, dashboard_url: str):
    page.goto(dashboard_url)
    page.evaluate("localStorage.removeItem('theme')")
    page.reload()

    kpi_label_size = page.eval_on_selector(".kpi-card p", "el => parseFloat(getComputedStyle(el).fontSize)")
    matrix_header_size = page.eval_on_selector("#matrixTable thead th", "el => parseFloat(getComputedStyle(el).fontSize)")
    sql_light = page.eval_on_selector("#source-sql", """el => {
        const style = getComputedStyle(el);
        return { fontSize: parseFloat(style.fontSize), background: style.backgroundColor };
    }""")
    zero_value_color = page.eval_on_selector(".matrix-row td:nth-child(2)", "el => getComputedStyle(el).color")

    assert kpi_label_size >= 12
    assert matrix_header_size >= 10
    assert sql_light["fontSize"] == 13
    assert zero_value_color == "rgb(100, 116, 139)"

    page.evaluate("localStorage.theme = 'dark'")
    page.reload()
    page.wait_for_timeout(300)  # Wait for transition-colors duration-200 to complete

    body_dark_background = page.eval_on_selector("body", "el => getComputedStyle(el).backgroundColor")
    sql_dark = page.eval_on_selector("#source-sql", """el => {
        const style = getComputedStyle(el);
        return { fontSize: parseFloat(style.fontSize), background: style.backgroundColor };
    }""")

    assert body_dark_background in ("rgb(13, 17, 23)", "rgb(11, 18, 32)", "rgb(12, 19, 33)")
    assert sql_dark["fontSize"] == 13
    assert sql_dark["background"] != sql_light["background"]
    assert sql_dark["background"] == "rgb(51, 65, 85)"

def test_orphans_tab_interaction(page: Page, dashboard_url: str):
    page.goto(dashboard_url)
    
    # Mock data for testing search/paging by mutating the properties of the const object
    page.evaluate("""
        unmatchedSrcData.columns = ['ID', 'NAME', 'VAL'];
        unmatchedSrcData.rows = [
            [1, 'Source Item A', 'Alpha'],
            [2, 'Source Item B', 'Beta'],
            [3, 'Source Item C', 'Gamma']
        ];
    """)
    
    # Click on the "Orphaned Records" tab
    page.locator("button[data-tab='tab-orphans']").click()
    
    # Verify the tab panel is active and showing Source Orphans
    expect(page.locator("#tab-orphans")).to_be_visible()
    expect(page.locator("#orphanTableTitle")).to_contain_text("Source Orphans")
    
    # Verify cards are visible
    expect(page.locator("text=Source Orphans").first).to_be_visible()
    
    # Verify mock rows are rendered in the table
    expect(page.locator("#orphanDataTable")).to_be_visible()
    expect(page.locator("#orphanTableBody tr")).to_have_count(3)
    
    # Search for an item in the search field while on Source Orphans
    search = page.locator("#orphanSearch")
    search.fill("Beta")
    expect(page.locator("#orphanTableBody tr")).to_have_count(1)
    
    search.fill("some_nonexistent_value_xyz")
    # Table should show empty state
    expect(page.locator("#orphanTableEmpty")).to_be_visible()
    expect(page.locator("#orphanDataTable")).to_be_hidden()
    
    # Clear search
    search.fill("")
    expect(page.locator("#orphanDataTable")).to_be_visible()
    expect(page.locator("#orphanTableBody tr")).to_have_count(3)

    # Click the second card (Target Orphans)
    page.locator("#tab-orphans .grid > div").nth(1).click()
    expect(page.locator("#orphanTableTitle")).to_contain_text("Target Orphans")

def test_sidebar_nav_active(page: Page, dashboard_url: str):
    page.goto(dashboard_url)

    # Test each sidebar link gets nav-active when clicked
    nav_tests = [
        ("#nav-kpi", "#kpi-section"),
        ("#nav-charts", "#charts"),
        ("#nav-matrix", "#matrix"),
        ("#nav-queries", "#test-queries"),
    ]

    for nav_id, section_id in nav_tests:
        page.locator(nav_id).click()
        page.wait_for_timeout(300)
        nav_class = page.locator(nav_id).get_attribute("class") or ""
        assert "nav-active" in nav_class, f"{nav_id} missing nav-active after clicking {section_id}"

def test_crosshair_column_highlight(page: Page, dashboard_url: str):
    page.goto(dashboard_url)
    page.wait_for_timeout(1000)

    # Toggle to light mode
    page.evaluate("document.documentElement.classList.remove('dark')")
    page.wait_for_timeout(300)

    # Find first data cell (column index 1 = second column, not Field)
    data_cell = page.locator("#matrixTable tbody tr.matrix-row:first-child td:nth-child(2)")
    assert data_cell.is_visible()

    col_idx = data_cell.evaluate("el => el.cellIndex")

    # Trigger mouseover on the cell
    data_cell.evaluate("el => el.dispatchEvent(new MouseEvent('mouseover', {bubbles: true}))")
    page.wait_for_timeout(100)

    # Verify column header has bg-indigo-100 class
    header_ok = page.evaluate(f"""() => {{
        const th = document.querySelector('#matrixTable thead tr th:nth-child({col_idx + 1})');
        return th ? th.classList.contains('bg-indigo-100') : false;
    }}""")
    assert header_ok, f"Column header (index {col_idx}) should have bg-indigo-100"

    # Verify column cell in another row has bg-indigo-50/60
    cell_ok = page.evaluate(f"""() => {{
        const rows = document.querySelectorAll('#matrixTable tbody tr.matrix-row');
        if (rows.length < 2) return false;
        return rows[1].cells[{col_idx}]?.classList.contains('bg-indigo-50/60') ?? false;
    }}""")
    assert cell_ok, f"Column cell in row 2 should have bg-indigo-50/60"


def test_crosshair_row_highlight(page: Page, dashboard_url: str):
    page.goto(dashboard_url)
    page.wait_for_timeout(1000)

    # Toggle to light mode
    page.evaluate("document.documentElement.classList.remove('dark')")
    page.wait_for_timeout(300)

    # Hover over a data cell
    data_cell = page.locator("#matrixTable tbody tr.matrix-row:first-child td:nth-child(3)")
    assert data_cell.is_visible()

    data_cell.evaluate("el => el.dispatchEvent(new MouseEvent('mouseover', {bubbles: true}))")
    page.wait_for_timeout(100)

    # Verify first cell in same row (Field column) has bg-sky-50/60
    row_ok = page.evaluate("""() => {
        const row = document.querySelector('#matrixTable tbody tr.matrix-row:first-child');
        if (!row || !row.cells[0]) return false;
        return row.cells[0].classList.contains('bg-sky-50/60');
    }""")
    assert row_ok, "Row cells should have bg-sky-50/60"

    # Verify border-y is present
    border_y_ok = page.evaluate("""() => {
        const row = document.querySelector('#matrixTable tbody tr.matrix-row:first-child');
        if (!row || !row.cells[0]) return false;
        return row.cells[0].classList.contains('border-y');
    }""")
    assert border_y_ok, "Row cells should have border-y"


def test_crosshair_clears_on_mouseleave(page: Page, dashboard_url: str):
    page.goto(dashboard_url)
    page.wait_for_timeout(1000)

    # Toggle to light mode
    page.evaluate("document.documentElement.classList.remove('dark')")
    page.wait_for_timeout(300)

    # Apply crosshair by hovering over a cell
    data_cell = page.locator("#matrixTable tbody tr.matrix-row:first-child td:nth-child(2)")
    col_idx = data_cell.evaluate("el => el.cellIndex")

    data_cell.evaluate("el => el.dispatchEvent(new MouseEvent('mouseover', {bubbles: true}))")
    page.wait_for_timeout(100)

    # Verify classes are applied
    header_ok = page.evaluate(f"""() => {{
        const th = document.querySelector('#matrixTable thead tr th:nth-child({col_idx + 1})');
        return th ? th.classList.contains('bg-indigo-100') : false;
    }}""")
    assert header_ok, "Classes should be applied before mouseleave"

    # Trigger mouseleave on the table
    page.evaluate("""() => {
        const table = document.querySelector('#matrixTable');
        if (table) table.dispatchEvent(new MouseEvent('mouseleave', {bubbles: true}));
    }""")
    page.wait_for_timeout(100)

    # Verify classes are removed
    header_gone = page.evaluate(f"""() => {{
        const th = document.querySelector('#matrixTable thead tr th:nth-child({col_idx + 1})');
        return th ? th.classList.contains('bg-indigo-100') : false;
    }}""")
    assert not header_gone, "Column header class should be removed after mouseleave"


def test_excel_report_button_exists(page: Page, dashboard_url: str):
    page.goto(dashboard_url)
    btn = page.locator("#excel-report-btn")
    expect(btn).to_be_visible()
    expect(btn).to_contain_text("Excel Report")
    expect(btn).to_have_attribute("title", "Download Full Excel Report")
    expect(page.locator("nav #excel-report-btn")).to_be_visible()


def test_excel_report_button_position(page: Page, dashboard_url: str):
    page.goto(dashboard_url)
    order = page.evaluate("""() => {
        const links = document.querySelectorAll('nav a');
        let queriesIdx = -1, btnIdx = -1;
        links.forEach((a, i) => {
            if (a.id === 'nav-queries') queriesIdx = i;
            if (a.id === 'excel-report-btn') btnIdx = i;
        });
        return { queriesIdx, btnIdx };
    }""")
    assert order['btnIdx'] > order['queriesIdx'], "Excel Report must appear after Test Queries in nav"
    expect(page.locator("nav .sidebar-section-label:has-text('Downloads')")).to_be_visible()


def test_automation_team_label(page: Page, dashboard_url: str):
    page.goto(dashboard_url)
    expect(page.locator("text=Automation Team")).to_be_visible()
    expect(page.locator("text=System Admin")).to_be_hidden()


def test_excel_report_content(page: Page, dashboard_url: str):
    page.goto(dashboard_url)
    with page.expect_download() as download_info:
        page.locator("#excel-report-btn").click()
    download = download_info.value
    assert download.suggested_filename == "tosca_integrity_report_full.xlsx"

    import tempfile, os
    import openpyxl
    tmp = tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False)
    tmp.close()
    try:
        download.save_as(tmp.name)
        wb = openpyxl.load_workbook(tmp.name)
        assert len(wb.sheetnames) == 17, f"Expected 17 sheets, got {len(wb.sheetnames)}"
        assert wb.sheetnames[0] == "Summary"
        assert wb.sheetnames[-1] == "All Issues"
        for et in ["Source Value is NULL", "Target Value is NULL",
                   "Null Equivalent Mismatch", "Duplicate Value Mismatch",
                   "Sorting Issue", "Whitespace Mismatch",
                   "Case Sensitivity Mismatch", "Type Coercion / Formatting",
                   "Boolean Format Mismatch", "Encoding / Special Char Mismatch",
                   "Precision / Rounding", "Data Truncation",
                   "Date/Timestamp Mismatch", "Numeric Data Mismatch",
                   "String Data Mismatch"]:
            safe = et.replace('/', '-')[:31]
            assert safe in wb.sheetnames, f"Missing sheet: {et}"
        ws = wb["Summary"]
        assert ws.max_column == 17, f"Summary expected 17 cols, got {ws.max_column}"
        assert ws.cell(1, 1).value == "Column Name", f"Expected 'Column Name' at A1, got {ws.cell(1, 1).value}"
        assert ws.cell(1, 17).value == "Total"
        ws_all = wb["All Issues"]
        assert ws_all.max_column == 5
        assert ws_all.max_row > 1000, f"All Issues expected >1000 rows, got {ws_all.max_row}"
        assert ws_all.cell(1, 3).value == "Error Type"
        ws_tn = wb["Target Value is NULL"]
        assert ws_tn.max_row > 100, f"Target Value is NULL expected >100 rows, got {ws_tn.max_row}"
        assert ws_tn.cell(1, 1).value == "Row Key"
        wb.close()
    finally:
        os.unlink(tmp.name)


def test_mismatch_type_dropdown_filter(page: Page, dashboard_url: str):
    page.goto(dashboard_url)
    
    # Get total count of rows
    initial_rows = page.locator(".matrix-row:visible").count()
    
    # Select "Whitespace Mismatch" (value = "6")
    page.locator("#mismatchTypeFilter").select_option("6")
    
    # Check if filters badge is visible
    expect(page.locator("#activeFiltersBadge")).to_be_visible()
    expect(page.locator("#activeFiltersText")).to_contain_text("Type:")
    
    # Reset filters using clear button
    page.locator("#activeFiltersBadge button").click()
    
    # Count rows should return to initial
    expect(page.locator("#activeFiltersBadge")).to_be_hidden()
    assert page.locator(".matrix-row:visible").count() == initial_rows

def test_bar_chart_click_filters_matrix(page: Page, dashboard_url: str):
    page.goto(dashboard_url)
    
    # Trigger click on first bar (index 0)
    page.evaluate("barChart.options.onClick(null, [{index: 0}])")
    
    # Check if matrix is filtered (search input is set to first label)
    first_label = page.evaluate("barChart.data.labels[0]")
    search_val = page.locator("#matrixSearch").input_value()
    assert search_val == first_label
    
    # Active filters badge must be visible and contains the first label
    expect(page.locator("#activeFiltersBadge")).to_be_visible()
    expect(page.locator("#activeFiltersText")).to_contain_text(first_label)


def test_matrix_columns_alignment(page: Page, dashboard_url: str):
    page.goto(dashboard_url)
    page.wait_for_timeout(1000)  # wait for page to render and stabilize
    
    ths = page.locator("#matrixTable > thead > tr > th").all()
    first_row_cells = page.locator("#matrixTable > tbody > tr.matrix-row").first.locator("> td").all()
    
    # Ensure we have the same number of columns in header and body
    assert len(ths) == 18
    assert len(first_row_cells) == 18
    
    for idx in range(18):
        th_box = ths[idx].bounding_box()
        td_box = first_row_cells[idx].bounding_box()
        
        assert th_box is not None
        assert td_box is not None
        
        # Check that the horizontal start coordinate (x) aligns within a 1.5px tolerance
        assert abs(th_box["x"] - td_box["x"]) < 1.5, f"Column at index {idx} is misaligned! Header X: {th_box['x']:.2f}, Body Cell X: {td_box['x']:.2f}"


def test_sticky_columns_opacity(page: Page, dashboard_url: str):
    page.goto(dashboard_url)
    page.wait_for_timeout(1000)  # Wait for page layout
    
    # Test light mode first
    page.evaluate("document.documentElement.classList.remove('dark')")
    page.wait_for_timeout(300)
    
    sticky_headers = [
        page.locator("#matrixTable > thead > tr > th.sticky.left-0"),
        page.locator("#matrixTable > thead > tr > th.matrix-sticky-total"),
        page.locator("#matrixTable > thead > tr > th.matrix-sticky-pct")
    ]
    
    first_row = page.locator("#matrixTable > tbody > tr.matrix-row").first
    sticky_body_cells = [
        first_row.locator("> td.sticky.left-0"),
        first_row.locator("> td.matrix-sticky-total"),
        first_row.locator("> td.matrix-sticky-pct")
    ]
    
    # Check that they are fully opaque in light mode (no rgba background with alpha < 1)
    for locator in sticky_headers + sticky_body_cells:
        bg_color = locator.evaluate("el => getComputedStyle(el).backgroundColor")
        assert "rgba(" not in bg_color or ", 1)" in bg_color or "0)" in bg_color, f"Background color {bg_color} is semi-transparent!"
        
    # Toggle to dark mode
    page.evaluate("document.documentElement.classList.add('dark')")
    page.wait_for_timeout(300)
    
    # Check dark mode opacity
    for locator in sticky_headers + sticky_body_cells:
        bg_color = locator.evaluate("el => getComputedStyle(el).backgroundColor")
        assert "rgba(" not in bg_color or ", 1)" in bg_color or "0)" in bg_color, f"Dark mode background color {bg_color} is semi-transparent!"


def test_matrix_table_layout_and_widths(page: Page, dashboard_url: str):
    page.goto(dashboard_url)
    
    # Verify table border-collapse is separate to fix scrolling bug
    table_css = page.eval_on_selector("#matrixTable", "el => getComputedStyle(el).borderCollapse")
    assert table_css == "separate"
    
    # Verify exact widths of columns to prevent overlapping
    # Field column
    field_width = page.eval_on_selector("#matrixTable th:nth-child(1)", "el => getComputedStyle(el).width")
    assert math.isclose(float(field_width.replace("px", "")), 270.0, abs_tol=5.0)
    
    # Src NULL column
    src_null_width = page.eval_on_selector("#matrixTable th:nth-child(2)", "el => getComputedStyle(el).width")
    assert math.isclose(float(src_null_width.replace("px", "")), 76.0, abs_tol=5.0)
    
    # Total column
    total_width = page.eval_on_selector("#matrixTable th:nth-child(17)", "el => getComputedStyle(el).width")
    assert math.isclose(float(total_width.replace("px", "")), 127.234, abs_tol=5.0)
    
    # Pct column
    pct_width = page.eval_on_selector("#matrixTable th:nth-child(18)", "el => getComputedStyle(el).width")
    assert math.isclose(float(pct_width.replace("px", "")), 73.0, abs_tol=5.0)

import math

def test_matrix_scrolling(page: Page, dashboard_url: str):
    page.goto(dashboard_url)
    
    container = page.locator('.overflow-x-auto.relative.scroll-smooth.rounded-b-2xl')
    page.wait_for_timeout(1000)
    
    # Get initial positions
    field_th_x_initial = page.locator('#matrixTable > thead > tr > th:nth-child(1)').bounding_box()['x']
    src_null_th_x_initial = page.locator('#matrixTable > thead > tr > th:nth-child(2)').bounding_box()['x']
    
    # Scroll right by 500px
    container.evaluate('el => el.scrollLeft = 500')
    page.wait_for_timeout(1000)
    
    # Get new positions
    field_th_x_final = page.locator('#matrixTable > thead > tr > th:nth-child(1)').bounding_box()['x']
    src_null_th_x_final = page.locator('#matrixTable > thead > tr > th:nth-child(2)').bounding_box()['x']
    
    # The sticky FIELD column must not move relative to the viewport
    assert math.isclose(field_th_x_final, field_th_x_initial, abs_tol=1.0), f"Sticky FIELD column moved! Initial x: {field_th_x_initial}, Final x: {field_th_x_final}"
    
    # The non-sticky SRC NULL column must have moved to the left
    assert src_null_th_x_final < src_null_th_x_initial, f"SRC NULL column did not move left! Initial x: {src_null_th_x_initial}, Final x: {src_null_th_x_final}"
    
    # Verify that FIELD z-index is greater than SRC NULL z-index so it stays on top
    field_z = page.evaluate('getComputedStyle(document.querySelector("#matrixTable > thead > tr > th:nth-child(1)")).zIndex')
    src_null_z = page.evaluate('getComputedStyle(document.querySelector("#matrixTable > thead > tr > th:nth-child(2)")).zIndex')
    
    assert int(field_z) > int(src_null_z), f"FIELD z-index ({field_z}) is not greater than SRC NULL z-index ({src_null_z})"

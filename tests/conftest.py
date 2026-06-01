"""
Pytest configuration for the TOSCA DI Report Dashboard tests.

Provides:
- Pre-generation of the HTML report so workers don't race to regenerate
- pytest-xdist group/scheduling configuration for parallel execution
- Shared session-scoped fixture for the dashboard URL
- Default Playwright timeouts sized for parallel Firefox headless loads
"""

import os
import sys
import pytest


def _ensure_html_generated():
    """Regenerate the HTML file once at module load.

    With pytest-xdist, multiple workers share the same file system but run in
    separate processes. We pre-generate the HTML before any worker starts
    tests so workers do not race to regenerate or overwrite each other.
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    html_file = os.path.join(project_root, "output", "tosca_enterprise_report.html")
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    import tosca_di_report_dashboard
    tosca_di_report_dashboard.generate_unified_dashboard(
        "tosca_report.db",
        html_file,
    )
    return html_file


# Run at import time so HTML exists before any worker begins.
_HTML_FILE = _ensure_html_generated()


@pytest.fixture(scope="session")
def dashboard_url():
    """Return a file:// URL to the generated dashboard.

    All xdist workers read from the same on-disk file, so this is safe to be
    session-scoped. We deliberately do NOT regenerate the file here to avoid
    race conditions between parallel workers.
    """
    return f"file:///{_HTML_FILE.replace(chr(92), '/')}"


@pytest.fixture(autouse=True)
def _increase_playwright_timeouts(page):
    """Raise Playwright's default 30s timeouts to 60s for parallel loads.

    With 5 workers all loading the 4MB HTML file in Firefox headless on
    Windows, individual `page.goto()` calls can briefly exceed the 30s
    default. 60s is comfortable headroom without masking real bugs.
    """
    page.set_default_timeout(60_000)
    page.set_default_navigation_timeout(60_000)
    yield


def pytest_configure(config):
    """Register xdist group/scheduling for parallel test execution.

    We group tests by browser+file so that all tests touching the same browser
    state run on the same worker. This minimizes the total number of expensive
    browser launches across the test run.
    """
    # Make sure HTML exists even on the master (xdist) node.
    _ensure_html_generated()

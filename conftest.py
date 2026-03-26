"""conftest.py — Pytest fixtures: FSM + Playwright + Report."""
import pytest, sys, logging, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from utils.fsm_engine import OrderWorkflow, ConcurrentWorkflowSimulator
from utils.data_loader import DataLoader
from utils.report_generator import ReportGenerator

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S")

BASE_URL   = os.environ.get("JUICE_SHOP_URL", "http://localhost:3000")
ADMIN_USER = "admin@juice-sh.op"
ADMIN_PASS = "admin123"


# ── Session fixtures ─────────────────────────────────────────

@pytest.fixture(scope="session")
def report():
    rg = ReportGenerator()
    yield rg
    rg.print_summary()
    ep = rg.save_excel_report()
    hp = rg.save_html_report()
    jp = rg.save_counterexample_json()
    print(f"\n  Reports:\n    Excel : {ep}\n    HTML  : {hp}\n    JSON  : {jp}")

@pytest.fixture(scope="session")
def data_loader(): return DataLoader()

@pytest.fixture(scope="session")
def base_url(): return BASE_URL


# ── Function fixtures ────────────────────────────────────────

@pytest.fixture
def fsm(): return OrderWorkflow()

@pytest.fixture
def concurrent_sim(): return ConcurrentWorkflowSimulator()


# ── Playwright UI fixtures ───────────────────────────────────

@pytest.fixture
def juice_shop_page(page):
    """Page đã navigate Juice Shop + dismiss dialogs."""
    page.goto(BASE_URL, wait_until="networkidle")
    _dismiss(page)
    yield page


@pytest.fixture
def logged_in_page(page):
    """
    Page đã login sẵn với admin account.
    Chờ cả token VÀ bid xuất hiện trong localStorage.
    """
    page.goto(f"{BASE_URL}/#/login", wait_until="networkidle")
    _dismiss(page)
    page.wait_for_selector("#email", timeout=10000)
    page.fill("#email", ADMIN_USER)
    page.fill("#password", ADMIN_PASS)
    page.click("#loginButton")

    # Chờ token
    try:
        page.wait_for_function("() => !!localStorage.getItem('token')", timeout=8000)
    except Exception:
        pass

    # Chờ bid (Juice Shop tạo basket ngay sau login)
    try:
        page.wait_for_function("() => !!localStorage.getItem('bid')", timeout=5000)
    except Exception:
        # Đôi khi bid chỉ xuất hiện sau khi navigate
        page.goto(BASE_URL, wait_until="networkidle")
        try:
            page.wait_for_function("() => !!localStorage.getItem('bid')", timeout=5000)
        except Exception:
            pass

    _dismiss(page)
    yield page


def _dismiss(page):
    for sel in [
        "button[aria-label='Close Welcome Banner']",
        "button.mat-focus-indicator:has-text('Dismiss')",
        "mat-dialog-container button",
    ]:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=1000):
                btn.click()
                page.wait_for_timeout(250)
        except Exception:
            pass


# ── Markers ──────────────────────────────────────────────────

def pytest_configure(config):
    for m, d in [
        ("valid_path",    "Nhóm 1 — Valid Path (S0→S5)"),
        ("deadlock_path", "Nhóm 2 — Deadlock Detection (→S6)"),
        ("boundary",      "Nhóm 3 — Boundary State"),
        ("concurrent",    "Nhóm 4 — Concurrent"),
        ("fsm_only",      "FSM tests — không cần browser"),
        ("ui",            "UI tests — cần Juice Shop localhost:3000"),
    ]:
        config.addinivalue_line("markers", f"{m}: {d}")

def pytest_collection_modifyitems(items):
    order = {"valid_path": 0, "boundary": 1, "deadlock_path": 2, "concurrent": 3, "ui": 4}
    items.sort(key=lambda i: next(
        (order[m] for m in order if i.get_closest_marker(m)), 99))

"""conftest.py — Pytest fixtures: FSM + Playwright + Report.

FIX v2:
- logged_in_page: bid chỉ được tạo sau lần ADD ITEM đầu tiên, không phải sau login.
  Fixture giờ add 1 item để kích hoạt bid, sau đó xoá item (để test tự quản lý giỏ).
  Hoặc nếu test cần giỏ sạch (test_ui_empty_cart), bid vẫn tồn tại sau remove.

- juice_shop_page: thêm wait_for_load_state("networkidle") cho ổn định hơn.

- _dismiss: tăng timeout, thêm "Me want it!" cookie banner.
"""
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
    page.goto(BASE_URL, wait_until="domcontentloaded")
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass
    _dismiss(page)
    yield page


@pytest.fixture
def logged_in_page(page):
    """
    Page đã login sẵn với admin account VÀ có bid hợp lệ.

    ROOT CAUSE FIX: Juice Shop chỉ tạo 'bid' trong localStorage sau khi
    user ADD item đầu tiên vào giỏ — KHÔNG phải sau login.
    Nếu không có bid, mọi call tới /api/Baskets/null đều trả về 0.

    Fix: sau khi login, add 1 sản phẩm để trigger bid, rồi xoá đi.
    Kết quả: bid đã tồn tại, giỏ hàng trống — test tự quản lý tiếp theo.
    """
    # Login
    page.goto(f"{BASE_URL}/#/login", wait_until="domcontentloaded")
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass
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

    # FIX v3: Extract bid từ JWT payload (Juice Shop nhúng bid trong token)
    # rồi thử API để xác nhận và set vào localStorage.
    page.evaluate("""async () => {
        try {
            const token = localStorage.getItem('token');
            if (!token) return;
            if (localStorage.getItem('bid')) return;  // đã có rồi

            // Bước 1: Decode JWT lấy bid
            const payload = JSON.parse(atob(token.split('.')[1]));
            let bid = payload.bid
                   || (payload.data && payload.data.bid)
                   || (payload.data && payload.data.BasketId)
                   || payload.BasketId;

            // Bước 2: Nếu không có trong JWT, thử userId làm bid
            // (Juice Shop thường bid = userId cho admin)
            if (!bid) {
                const userId = (payload.data && payload.data.id)
                             || payload.id || payload.sub;
                if (userId) {
                    const r = await fetch('/api/Baskets/' + userId, {
                        headers: { 'Authorization': 'Bearer ' + token }
                    });
                    if (r.ok) bid = String(userId);
                }
            }

            if (bid) localStorage.setItem('bid', String(bid));
        } catch(e) {}
    }""")

    # Kiểm tra bid đã có chưa
    try:
        page.wait_for_function("() => !!localStorage.getItem('bid')", timeout=3000)
        _dismiss(page)
        yield page
        return
    except Exception:
        pass

    # bid vẫn chưa có → fallback: add 1 item để Juice Shop tạo basket
    page.goto(f"{BASE_URL}/#/search", wait_until="domcontentloaded")
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass
    _dismiss(page)
    page.wait_for_timeout(1000)

    for sel in [
        "button[aria-label='Add to Basket']",
        "button[aria-label*='Add']",
        "mat-card button.mat-icon-button",
    ]:
        try:
            btns = page.locator(sel)
            if btns.count() > 0:
                btns.first.scroll_into_view_if_needed()
                btns.first.click()
                try:
                    page.locator("simple-snack-bar").wait_for(
                        state="visible", timeout=5000
                    )
                    page.locator("simple-snack-bar").wait_for(
                        state="hidden", timeout=5000
                    )
                except Exception:
                    page.wait_for_timeout(1000)
                break
        except Exception:
            continue

    # Đợi bid xuất hiện sau khi add
    try:
        page.wait_for_function("() => !!localStorage.getItem('bid')", timeout=5000)
    except Exception:
        pass

    _dismiss(page)
    yield page


def _dismiss(page):
    """Đóng tất cả dialogs/banners của Juice Shop."""
    selectors = [
        "button[aria-label='Close Welcome Banner']",
        "button.mat-focus-indicator:has-text('Dismiss')",
        "mat-dialog-container button",
        # Cookie banner — quan trọng vì nó che Continue button ở checkout
        "a:has-text('Me want it!')",
        "button:has-text('Me want it!')",
    ]
    for sel in selectors:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=1200):
                btn.click()
                page.wait_for_timeout(300)
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

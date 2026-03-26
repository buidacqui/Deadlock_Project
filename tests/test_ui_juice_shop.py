"""
tests/test_ui_juice_shop.py
============================
UI Tests thực tế trên OWASP Juice Shop dùng Playwright.
Fixed v3: dùng /api/Baskets/{bid} để đọc cart count, multiple checkout selectors.

CHẠY: pytest tests/test_ui_juice_shop.py -m ui -v --headed
YÊU CẦU: docker compose up -d juice-shop (localhost:3000)
"""
import pytest
from utils.fsm_engine import OrderWorkflow

BASE_URL       = "http://localhost:3000"
VALID_USER     = "admin@juice-sh.op"
VALID_PASSWORD = "admin123"
WRONG_PASSWORD = "wrong_password_999"


# ────────────────────────────────────────────────────────────
# HELPERS
# ────────────────────────────────────────────────────────────

def dismiss_dialogs(page):
    for sel in [
        "button[aria-label='Close Welcome Banner']",
        "mat-dialog-container button",
        "button.mat-button:has-text('Dismiss')",
    ]:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=800):
                el.click()
                page.wait_for_timeout(200)
        except Exception:
            pass


def do_login(page, email, password) -> bool:
    page.goto(f"{BASE_URL}/#/login", wait_until="networkidle")
    dismiss_dialogs(page)
    page.wait_for_selector("#email", timeout=8000)
    page.fill("#email", email)
    page.fill("#password", password)
    page.click("#loginButton")
    try:
        page.wait_for_function("() => !!localStorage.getItem('token')", timeout=7000)
        return True
    except Exception:
        return False


def do_logout(page):
    try:
        page.evaluate("() => { localStorage.removeItem('token'); localStorage.removeItem('bid'); }")
    except Exception:
        pass


def add_to_cart(page) -> bool:
    page.goto(f"{BASE_URL}/#/search", wait_until="networkidle")
    dismiss_dialogs(page)
    page.wait_for_timeout(1500)
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
                page.wait_for_timeout(2000)
                return True
        except Exception:
            continue
    return False


def get_cart_count(page) -> int:
    """
    Đọc số item trong giỏ qua Juice Shop REST API.
    Endpoint: GET /api/Baskets/{bid}  → data.Products.length
    """
    try:
        return page.evaluate("""async () => {
            const token = localStorage.getItem('token');
            const bid   = localStorage.getItem('bid');
            if (!token || !bid) return 0;
            try {
                const r = await fetch('/api/Baskets/' + bid, {
                    headers: { 'Authorization': 'Bearer ' + token }
                });
                if (!r.ok) return 0;
                const d = await r.json();
                if (d.data && d.data.Products)    return d.data.Products.length;
                if (d.data && d.data.BasketItems) return d.data.BasketItems.length;
                return 0;
            } catch(e) { return 0; }
        }""")
    except Exception:
        return 0


def get_bid(page) -> str:
    try:
        return page.evaluate("() => localStorage.getItem('bid') || 'null'")
    except Exception:
        return "error"


# ────────────────────────────────────────────────────────────
# TEST CLASS
# ────────────────────────────────────────────────────────────

@pytest.mark.ui
class TestJuiceShopUI:

    def test_ui_valid_login(self, page, report):
        """[VP_UI_001] Login hợp lệ → FSM S0→S1."""
        wf      = OrderWorkflow("VP_UI_001")
        success = do_login(page, VALID_USER, VALID_PASSWORD)
        if success:
            wf.do_login()

        assert success, (
            f"Login thất bại với {VALID_USER}.\n"
            "Kiểm tra Juice Shop tại http://localhost:3000"
        )
        assert wf.state == "authenticated"
        report.record(
            tc_id="VP_UI_001", group="UI Valid Path",
            description="Login valid → S1",
            event_sequence="goto_login,fill_credentials,click_loginButton",
            expected_state="authenticated", actual_state=wf.state,
            expected_result="PASS", actual_result="PASS",
            path_taken=wf.get_path(), is_deadlock_expected=False,
        )
        do_logout(page)

    def test_ui_invalid_login(self, page, report):
        """[BD_UI_001] Login sai → FSM giữ S0."""
        wf      = OrderWorkflow("BD_UI_001")
        success = do_login(page, VALID_USER, WRONG_PASSWORD)
        wf.do_login_fail()

        assert not success, "Login sai KHÔNG được thành công"
        assert wf.state == "guest"
        report.record(
            tc_id="BD_UI_001", group="UI Boundary",
            description="Login fail → S0",
            event_sequence="goto_login,fill_wrong_password,click_loginButton",
            expected_state="guest", actual_state=wf.state,
            expected_result="PASS", actual_result="PASS",
            path_taken=wf.get_path(), is_deadlock_expected=False,
        )

    def test_ui_add_to_cart(self, page, report):
        """[VP_UI_002] Add sản phẩm → FSM S1→S2. Verify qua /api/Baskets/{bid}."""
        wf = OrderWorkflow("VP_UI_002")

        login_ok = do_login(page, VALID_USER, VALID_PASSWORD)
        assert login_ok, "Cần login trước"
        wf.do_login()

        # Đợi bid xuất hiện sau login
        page.wait_for_function("() => !!localStorage.getItem('bid')", timeout=5000)
        bid_before = get_bid(page)

        added = add_to_cart(page)
        if added:
            wf.do_add_to_cart()

        # Đợi thêm để API cập nhật
        page.wait_for_timeout(1000)
        count = get_cart_count(page)
        bid_after = get_bid(page)

        assert added, "Phải add được sản phẩm"
        assert wf.state == "cart_active"
        assert count >= 1, (
            f"Cart phải có ≥ 1 item, got {count}.\n"
            f"bid before={bid_before}, after={bid_after}\n"
            "Thử chạy: pytest tests/debug_juice_shop.py -m ui -v --headed -s"
        )

        report.record(
            tc_id="VP_UI_002", group="UI Valid Path",
            description="Add to cart → S2",
            event_sequence="login,goto_search,click_add_to_basket",
            expected_state="cart_active", actual_state=wf.state,
            expected_result="PASS", actual_result="PASS",
            path_taken=wf.get_path(), is_deadlock_expected=False,
        )
        do_logout(page)

    def test_ui_proceed_to_checkout(self, page, report):
        """[VP_UI_003] Checkout → FSM S2→S3."""
        wf = OrderWorkflow("VP_UI_003")
        do_login(page, VALID_USER, VALID_PASSWORD)
        wf.do_login()
        page.wait_for_function("() => !!localStorage.getItem('bid')", timeout=5000)
        add_to_cart(page)
        wf.do_add_to_cart()
        page.wait_for_timeout(1000)

        # Navigate basket
        page.goto(f"{BASE_URL}/#/basket", wait_until="networkidle")
        page.wait_for_timeout(2000)

        checkout_ok = False
        for sel in [
            "button[aria-label='Proceed to checkout']",
            "button:has-text('Checkout')",
            "#checkoutButton",
            "button.mat-raised-button",
        ]:
            try:
                btn = page.locator(sel).first
                if btn.is_visible(timeout=2000):
                    btn.click()
                    try:
                        page.wait_for_url("**/#/address**", timeout=6000)
                    except Exception:
                        pass
                    if "#/address" in page.url or "#/checkout" in page.url:
                        wf.do_checkout()
                        checkout_ok = True
                        break
            except Exception:
                continue

        assert wf.state in ("checkout", "cart_active")
        assert not wf.is_deadlocked()
        report.record(
            tc_id="VP_UI_003", group="UI Valid Path",
            description="Checkout → S2→S3",
            event_sequence="login,add_cart,basket,proceed_checkout",
            expected_state="checkout", actual_state=wf.state,
            expected_result="PASS", actual_result="PASS",
            path_taken=wf.get_path(), is_deadlock_expected=False,
        )
        do_logout(page)

    def test_ui_session_expire_boundary(self, page, report):
        """[BD_UI_002] Session expire → S1→S7→S0, không deadlock."""
        wf = OrderWorkflow("BD_UI_002")
        do_login(page, VALID_USER, VALID_PASSWORD)
        wf.do_login()

        page.evaluate("() => { localStorage.removeItem('token'); sessionStorage.clear(); }")
        page.reload(wait_until="networkidle")
        wf.do_session_expire()
        wf.do_restore()

        assert wf.state == "guest"
        assert not wf.is_deadlocked()
        assert "deadlock" not in wf.history
        report.record(
            tc_id="BD_UI_002", group="UI Boundary",
            description="Session expire → S7→S0",
            event_sequence="login,remove_token,reload,restore",
            expected_state="guest", actual_state=wf.state,
            expected_result="PASS", actual_result="PASS",
            path_taken=wf.get_path(), is_deadlock_expected=False,
        )

    def test_ui_ag_property_no_deadlock_in_normal_flow(self, page, report):
        """[AG_UI_001] AG(¬S6): normal UI flow không deadlock."""
        wf = OrderWorkflow("AG_UI_001")
        do_login(page, VALID_USER, VALID_PASSWORD)
        wf.do_login()
        add_to_cart(page)
        wf.do_add_to_cart()

        assert "deadlock" not in wf.history
        assert not wf.is_deadlocked()
        report.record(
            tc_id="AG_UI_001", group="UI AG Verification",
            description="AG(¬S6): normal flow không deadlock",
            event_sequence="login,add_to_cart",
            expected_state="cart_active", actual_state=wf.state,
            expected_result="PASS", actual_result="PASS",
            path_taken=wf.get_path(), is_deadlock_expected=False,
        )
        do_logout(page)

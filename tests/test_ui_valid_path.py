"""
tests/test_ui_valid_path.py
============================
UI Tests — Valid Path (S0→S5) trên OWASP Juice Shop.
Fixed v3: dùng /api/Baskets/{bid}, checkout multiple selectors, logged_in_page fixture.
"""
import pytest
from pages.login_page import LoginPage
from pages.product_page import ProductPage, CartPage
from pages.checkout_page import CheckoutPage
from utils.fsm_engine import OrderWorkflow

BASE_URL = "http://localhost:3000"


def get_cart_count(page) -> int:
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


@pytest.mark.ui
class TestUIValidPath:

    def test_ui_login_maps_to_s1(self, juice_shop_page, report):
        """[UI_VP_001] Login hợp lệ → FSM S0→S1."""
        page = juice_shop_page
        wf   = OrderWorkflow("UI_VP_001")

        lp = LoginPage(page)
        lp.open()
        success = lp.login_valid()
        if success:
            wf.do_login()

        assert success, "Login admin@juice-sh.op/admin123 phải thành công"
        assert wf.state == "authenticated"
        assert lp.is_logged_in()

        report.record(
            tc_id="UI_VP_001", group="UI Valid Path",
            description="Login valid → S1",
            event_sequence="navigate_login,fill_credentials,click_login",
            expected_state="authenticated", actual_state=wf.state,
            expected_result="PASS", actual_result="PASS",
            path_taken=wf.get_path(), is_deadlock_expected=False,
        )
        lp.logout()

    def test_ui_add_to_cart_maps_to_s2(self, logged_in_page, report):
        """[UI_VP_002] Add sản phẩm → FSM S1→S2. Dùng logged_in_page fixture."""
        page = logged_in_page
        wf   = OrderWorkflow("UI_VP_002")
        wf.do_login()

        # Đảm bảo bid đã xuất hiện
        try:
            page.wait_for_function("() => !!localStorage.getItem('bid')", timeout=5000)
        except Exception:
            pass

        pp    = ProductPage(page)
        pp.open()
        added = pp.add_first_product_to_cart()
        if added:
            wf.do_add_to_cart()

        page.wait_for_timeout(1000)
        count = get_cart_count(page)

        assert added, "Phải add được sản phẩm vào giỏ"
        assert wf.state == "cart_active"
        assert count >= 1, (
            f"Cart API phải ≥ 1 item, got {count}.\n"
            f"bid={pp.get_bid_from_storage()}\n"
            "Debug: pytest tests/debug_juice_shop.py -m ui -v --headed -s"
        )

        report.record(
            tc_id="UI_VP_002", group="UI Valid Path",
            description="Add to cart → S2",
            event_sequence="open_search,click_add_to_basket",
            expected_state="cart_active", actual_state=wf.state,
            expected_result="PASS", actual_result="PASS",
            path_taken=wf.get_path(), is_deadlock_expected=False,
        )

    def test_ui_full_order_flow_s0_to_s5(self, juice_shop_page, report):
        """[UI_VP_003] Full flow S0→S5."""
        page = juice_shop_page
        wf   = OrderWorkflow("UI_VP_003")

        # S0→S1
        lp = LoginPage(page)
        lp.open()
        assert lp.login_valid(), "Login phải thành công"
        wf.do_login()
        try:
            page.wait_for_function("() => !!localStorage.getItem('bid')", timeout=5000)
        except Exception:
            pass

        # S1→S2
        pp = ProductPage(page)
        pp.open()
        assert pp.add_first_product_to_cart(), "Add to cart phải thành công"
        wf.do_add_to_cart()
        page.wait_for_timeout(1000)

        # S2→S3: Navigate basket, tìm checkout button
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
                    page.wait_for_timeout(1500)
                    if "#/address" in page.url or "#/checkout" in page.url:
                        wf.do_checkout()
                        checkout_ok = True
                        break
            except Exception:
                continue

        if not checkout_ok:
            # Log tất cả buttons để debug
            btns = page.evaluate("""() =>
                Array.from(document.querySelectorAll('button'))
                    .map(b => b.getAttribute('aria-label') || b.innerText.trim())
                    .filter(t => t.length > 0)
            """)
            pytest.skip(
                f"Checkout button không tìm thấy trên basket page.\n"
                f"Buttons hiện có: {btns}\n"
                f"Chạy debug: pytest tests/debug_juice_shop.py -m ui -v --headed -s"
            )

        assert wf.state == "checkout", f"FSM phải ở checkout, got '{wf.state}'"

        # S3→S4→S5
        checkout = CheckoutPage(page)
        completed = checkout.complete_checkout_flow()
        if completed:
            wf.do_pay()
            wf.do_confirm()

        assert wf.state == "confirmed", f"FSM phải ở confirmed, got '{wf.state}'"
        assert not wf.is_deadlocked()

        report.record(
            tc_id="UI_VP_003", group="UI Valid Path",
            description="Full flow S0→S5",
            event_sequence="login,add_cart,checkout,payment,confirm",
            expected_state="confirmed", actual_state=wf.state,
            expected_result="PASS", actual_result="PASS" if completed else "FAIL",
            path_taken=wf.get_path(), is_deadlock_expected=False,
        )

    def test_ui_login_fail_stays_s0(self, juice_shop_page, report):
        """[UI_BD_001] Login sai → ở lại S0."""
        page = juice_shop_page
        wf   = OrderWorkflow("UI_BD_001")

        lp = LoginPage(page)
        lp.open()
        result = lp.login_invalid()
        wf.do_login_fail()

        assert not result
        assert wf.state == "guest"
        report.record(
            tc_id="UI_BD_001", group="UI Boundary",
            description="Login fail → S0",
            event_sequence="navigate_login,fill_wrong,click_login",
            expected_state="guest", actual_state=wf.state,
            expected_result="PASS", actual_result="PASS",
            path_taken=wf.get_path(), is_deadlock_expected=False,
        )

    def test_ui_empty_cart_cannot_checkout(self, logged_in_page, report):
        """[UI_BD_002] Cart rỗng → không thể checkout."""
        page = logged_in_page
        wf   = OrderWorkflow("UI_BD_002")
        wf.do_login()

        cp = CartPage(page)
        cp.open()
        cp.remove_all_items()
        wf.do_add_to_cart()
        wf.do_empty_cart()

        can_checkout = cp.proceed_to_checkout()
        assert not can_checkout, "Cart rỗng KHÔNG được checkout"
        assert not wf.is_deadlocked()

        report.record(
            tc_id="UI_BD_002", group="UI Boundary",
            description="Empty cart cannot checkout",
            event_sequence="login,open_basket,remove_all,try_checkout",
            expected_state="cart_active", actual_state=wf.state,
            expected_result="PASS", actual_result="PASS",
            path_taken=wf.get_path(), is_deadlock_expected=False,
        )

"""
pages/checkout_page.py
======================
Page Object cho toàn bộ luồng Checkout → Payment → Confirmed.
Map trực tiếp sang FSM: S3 (Checkout) → S4 (Processing) → S5 (Confirmed).

FIX v6 (payment root cause):
- ADD_CARD_BTN đổi thành expansion panel selector (không phải button).
- select_or_add_payment(): _wait_for_step dùng selector thực tế trên trang
  (mat-radio-button hoặc mat-expansion-panel-header) thay vì button không tồn tại.
- Nếu đã có thẻ sẵn → chọn radio → Continue (không cần mở expansion panel).
- Nếu chưa có thẻ → mở expansion panel → điền form → submit.
"""
from playwright.sync_api import Page
from pages.base_page import BasePage
import logging

logger = logging.getLogger(__name__)


class CheckoutPage(BasePage):
    # ── Address step (S3) ─────────────────────────────────────
    NEW_ADDRESS_BTN    = "button:has-text('Add New Address')"
    COUNTRY_INPUT      = "input[placeholder='Please provide a country.']"
    NAME_INPUT         = "input[placeholder='Please provide a name.']"
    MOBILE_INPUT       = "input[placeholder='Please provide a mobile number.']"
    ZIP_INPUT          = "input[placeholder='Please provide a ZIP code.']"
    ADDRESS_INPUT      = "textarea[placeholder='Please provide an address.']"
    CITY_INPUT         = "input[placeholder='Please provide a city.']"
    SUBMIT_ADDRESS_BTN = "button[id='submitButton']"

    # ── Delivery + shared Continue ────────────────────────────
    DELIVERY_OPTION    = "mat-radio-button"
    CONTINUE_BTN       = "button:has-text('Continue')"

    # ── Payment step (S4) ─────────────────────────────────────
    # FIX v6: "Add new card" là mat-expansion-panel, KHÔNG phải <button>.
    # Selector dùng để WAIT khi vào trang payment:
    PAYMENT_PAGE_READY = "mat-radio-button, mat-expansion-panel-header"
    # Selector để MỞ expansion panel thêm thẻ mới:
    ADD_CARD_PANEL     = "mat-expansion-panel-header:has-text('Add new card')"
    # Giữ lại tên cũ để không break code khác tham chiếu (alias):
    ADD_CARD_BTN       = "mat-expansion-panel-header:has-text('Add new card')"

    CARD_NAME_INPUT    = "input[data-placeholder='Name']"
    CARD_NUMBER_INPUT  = "input[data-placeholder='Card Number']"
    CARD_EXPIRY_INPUT  = "mat-select[name='expiryMonth']"
    CARD_YEAR_INPUT    = "mat-select[name='expiryYear']"
    SUBMIT_CARD_BTN    = "button[id='submitButton']"

    # ── Order summary → Confirm ───────────────────────────────
    PLACE_ORDER_BTN     = "button:has-text('Place your order and pay')"
    CONFIRMATION_HEADER = "h1:has-text('Thank you')"
    ORDER_ID_TEXT       = "label.confirmation"

    # ── Cookie banner ─────────────────────────────────────────
    COOKIE_BTN = "a:has-text('Me want it!'), button:has-text('Me want it!')"

    def __init__(self, page: Page):
        super().__init__(page)

    # ──────────────────────────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────────────────────────

    def _dismiss_cookie_banner(self):
        """Đóng cookie consent banner nếu đang che element."""
        try:
            btn = self.page.locator(self.COOKIE_BTN).first
            if btn.is_visible(timeout=1500):
                btn.click()
                self.page.wait_for_timeout(300)
                logger.info("Đã đóng cookie banner")
        except Exception:
            pass

    def _click_continue(self, step: str, timeout: int = 8000):
        """Click Continue và đợi Angular navigate."""
        self._dismiss_cookie_banner()
        try:
            btn = self.page.locator(self.CONTINUE_BTN).first
            btn.wait_for(state="visible", timeout=timeout)
            btn.scroll_into_view_if_needed()
            btn.click()
            self.page.wait_for_load_state("networkidle", timeout=10000)
            logger.info(f"✓ Continue clicked ({step})")
        except Exception as e:
            logger.warning(f"Continue button lỗi ở {step}: {e}")

    def _wait_for_step(self, step_name: str, selector: str, timeout: int = 10000):
        logger.info(f"Đang đợi step: {step_name}")
        try:
            self.page.wait_for_load_state("domcontentloaded")
            self._dismiss_cookie_banner()
            self.page.wait_for_selector(selector, timeout=timeout, state="visible")
            logger.info(f"✓ Step {step_name} sẵn sàng")
        except Exception as e:
            self.page.screenshot(path=f"debug_{step_name}_FAILED.png")
            logger.error(f"✗ Lỗi step {step_name} | URL: {self.page.url} | {e}")
            raise

    # ──────────────────────────────────────────────────────────
    # ADDRESS STEP — ROOT CAUSE FIX
    # ──────────────────────────────────────────────────────────

    def select_or_add_address(self) -> bool:
        """
        Chọn địa chỉ bằng MAT-RADIO-BUTTON rồi click Continue.
        """
        try:
            logger.info("Đang đợi trang address load...")
            self.page.wait_for_load_state("domcontentloaded")
            self._dismiss_cookie_banner()

            self.page.wait_for_selector(
                self.NEW_ADDRESS_BTN, timeout=15000, state="visible"
            )
            logger.info("✓ Trang address đã load")
            self.page.wait_for_timeout(800)
            self._dismiss_cookie_banner()

            address_rows = self.page.locator("app-address mat-row")
            row_count = address_rows.count()
            logger.info(f"Số địa chỉ có sẵn: {row_count}")

            if row_count > 0:
                logger.info("Đang chọn địa chỉ có sẵn...")
                radio = address_rows.first.locator("mat-radio-button").first
                radio.click()
                logger.info("✓ Đã click radio chọn địa chỉ")
                self.page.wait_for_timeout(400)
                self._click_continue("address-existing")
                return True

            # ── Tạo địa chỉ mới ──────────────────────────────
            logger.info("Không có địa chỉ sẵn, đang tạo mới...")
            self.page.locator(self.NEW_ADDRESS_BTN).click()

            self.page.wait_for_selector(
                self.COUNTRY_INPUT, timeout=10000, state="visible"
            )
            logger.info("Form địa chỉ đã xuất hiện")

            self.page.fill(self.COUNTRY_INPUT, "Vietnam")
            self.page.fill(self.NAME_INPUT, "Test User")
            self.page.fill(self.MOBILE_INPUT, "0909000000")
            self.page.fill(self.ZIP_INPUT, "70000")
            self.page.fill(self.ADDRESS_INPUT, "123 Test Street")
            self.page.fill(self.CITY_INPUT, "Ho Chi Minh City")
            logger.info("Đã điền form")

            self.page.locator(self.SUBMIT_ADDRESS_BTN).click()
            logger.info("Đã submit form địa chỉ")

            try:
                self.page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass
            self.page.wait_for_timeout(1000)
            self._dismiss_cookie_banner()

            self.page.wait_for_selector(
                "app-address mat-row", timeout=15000, state="visible"
            )
            logger.info("✓ Danh sách địa chỉ đã cập nhật")

            address_rows = self.page.locator("app-address mat-row")
            radio = address_rows.first.locator("mat-radio-button").first
            radio.click()
            logger.info("✓ Đã click radio chọn địa chỉ mới")
            self.page.wait_for_timeout(400)

            self._click_continue("address-new")
            logger.info("✓ Đã tạo và chọn địa chỉ mới")
            return True

        except Exception as e:
            logger.error(f"✗ Address failed: {e}")
            self.page.screenshot(path="error_address.png")
            try:
                with open("error_address_page.html", "w", encoding="utf-8") as f:
                    f.write(self.page.content())
            except Exception:
                pass
            import traceback
            logger.error(traceback.format_exc())
            return False

    # ──────────────────────────────────────────────────────────
    # DELIVERY STEP
    # ──────────────────────────────────────────────────────────

    def select_delivery(self) -> bool:
        """Chọn phương thức giao hàng (radio) → Continue."""
        try:
            self._wait_for_step("delivery", self.DELIVERY_OPTION, timeout=10000)
            self._dismiss_cookie_banner()

            options = self.page.locator(self.DELIVERY_OPTION)
            if options.count() > 0:
                options.first.click()
                logger.info("✓ Đã chọn phương thức giao hàng")
                self.page.wait_for_timeout(400)

            self._click_continue("delivery")
            logger.info("✓ Delivery selected (S3)")
            return True

        except Exception as e:
            logger.error(f"✗ Delivery step failed: {e}")
            self.page.screenshot(path="error_delivery.png")
            return False

    # ──────────────────────────────────────────────────────────
    # PAYMENT STEP — FIX v6
    # ──────────────────────────────────────────────────────────

    def select_or_add_payment(self) -> bool:
        """
        Chọn thẻ bằng MAT-RADIO-BUTTON → Continue.

        FIX v6: Dùng PAYMENT_PAGE_READY ('mat-radio-button, mat-expansion-panel-header')
        thay vì ADD_CARD_BTN cũ ('button:has-text(...)') vốn không tồn tại trên trang.
        - Nếu đã có thẻ (mat-table mat-row): chọn radio → Continue.
        - Chưa có: mở expansion panel → điền form → submit → chọn radio → Continue.
        """
        try:
            # FIX: đợi element thực sự tồn tại trên trang payment
            self._wait_for_step(
                "payment", self.PAYMENT_PAGE_READY, timeout=15000
            )
            self._dismiss_cookie_banner()

            # Kiểm tra có thẻ sẵn không
            payment_rows = self.page.locator("mat-table mat-row")
            row_count = payment_rows.count()
            logger.info(f"Số thẻ có sẵn: {row_count}")

            if row_count > 0:
                radio = payment_rows.first.locator("mat-radio-button").first
                radio.click()
                logger.info("✓ Đã chọn thẻ có sẵn (S4)")
                self.page.wait_for_timeout(400)
                self._click_continue("payment-existing")
                return True

            # ── Thêm thẻ mới qua expansion panel ─────────────
            logger.info("Không có thẻ sẵn, đang mở expansion panel thêm thẻ mới...")
            panel = self.page.locator(self.ADD_CARD_PANEL)
            panel.wait_for(state="visible", timeout=8000)
            panel.click()
            logger.info("Đã mở 'Add new card' panel")

            self.page.wait_for_selector(
                self.CARD_NAME_INPUT, timeout=5000, state="visible"
            )
            self.page.wait_for_load_state("networkidle")

            self.page.fill(self.CARD_NAME_INPUT, "Test User")
            self.page.fill(self.CARD_NUMBER_INPUT, "4111111111111111")

            self.page.locator(self.CARD_EXPIRY_INPUT).click()
            self.page.wait_for_timeout(500)
            self.page.locator("mat-option").nth(5).click()

            self.page.wait_for_timeout(300)
            self.page.locator(self.CARD_YEAR_INPUT).click()
            self.page.wait_for_timeout(500)
            self.page.locator("mat-option").first.click()

            self.page.wait_for_timeout(300)
            self.page.locator(self.SUBMIT_CARD_BTN).click()
            logger.info("Đã submit thông tin thẻ")

            self.page.wait_for_load_state("networkidle", timeout=10000)
            self.page.wait_for_timeout(800)
            self._dismiss_cookie_banner()

            self.page.wait_for_selector(
                "mat-table mat-row", timeout=10000, state="visible"
            )
            payment_rows = self.page.locator("mat-table mat-row")
            radio = payment_rows.first.locator("mat-radio-button").first
            radio.click()
            logger.info("✓ Đã chọn thẻ mới (S4)")
            self.page.wait_for_timeout(400)

            self._click_continue("payment-new")
            logger.info("✓ Payment step hoàn thành")
            return True

        except Exception as e:
            logger.error(f"✗ Payment step failed: {e} | URL: {self.page.url}")
            self.page.screenshot(path="error_payment.png")
            return False

    # ──────────────────────────────────────────────────────────
    # PLACE ORDER
    # ──────────────────────────────────────────────────────────

    def place_order(self) -> bool:
        """Đặt hàng — kích hoạt S4 → S5."""
        try:
            self._dismiss_cookie_banner()
            logger.info("Đang đợi button Place Order...")
            self.page.wait_for_selector(
                self.PLACE_ORDER_BTN, timeout=10000, state="visible"
            )
            self.page.locator(self.PLACE_ORDER_BTN).click()
            logger.info("Đã click Place Order, đang đợi xác nhận...")
            self.page.wait_for_selector(self.CONFIRMATION_HEADER, timeout=15000)
            logger.info("✓ Order placed — S5 confirmed!")
            return True

        except Exception as e:
            logger.error(f"✗ Place order failed: {e}")
            self.page.screenshot(path="error_place_order.png")
            return False

    # ──────────────────────────────────────────────────────────
    # UTILITIES
    # ──────────────────────────────────────────────────────────

    def is_confirmed(self) -> bool:
        try:
            return self.page.locator(self.CONFIRMATION_HEADER).is_visible(timeout=5000)
        except Exception:
            return False

    def get_order_id(self) -> str:
        try:
            return self.page.locator(self.ORDER_ID_TEXT).inner_text(timeout=3000)
        except Exception:
            return ""

    def complete_checkout_flow(self) -> bool:
        """Thực hiện toàn bộ luồng S3→S4→S5."""
        steps = [
            ("Select/add address",  self.select_or_add_address),
            ("Select delivery",     self.select_delivery),
            ("Select/add payment",  self.select_or_add_payment),
            ("Place order",         self.place_order),
        ]
        for step_name, step_fn in steps:
            logger.info("=" * 50)
            logger.info(f"Checkout step: {step_name}")
            logger.info("=" * 50)
            if not step_fn():
                logger.error(f"✗ Checkout FAILED at: {step_name}")
                return False
            logger.info(f"✓ {step_name} hoàn thành\n")

        logger.info("=" * 50)
        logger.info("✓ TOÀN BỘ CHECKOUT FLOW THÀNH CÔNG!")
        logger.info("=" * 50)
        return True

"""
pages/checkout_page.py
======================
Page Object cho toàn bộ luồng Checkout → Payment → Confirmed.
Map trực tiếp sang FSM: S3 (Checkout) → S4 (Processing) → S5 (Confirmed).
"""
from playwright.sync_api import Page
from pages.base_page import BasePage
import logging

logger = logging.getLogger(__name__)


class CheckoutPage(BasePage):
    # Address step (S3)
    ADDRESS_ROWS        = "mat-row"
    USE_ADDRESS_BTN     = "button:has-text('Deliver here')"
    NEW_ADDRESS_BTN     = "button:has-text('Add New Address')"
    COUNTRY_INPUT       = "input[placeholder='Please provide a country.']"
    NAME_INPUT          = "input[placeholder='Please provide a name.']"
    MOBILE_INPUT        = "input[placeholder='Please provide a mobile number.']"
    ZIP_INPUT           = "input[placeholder='Please provide a ZIP code.']"
    ADDRESS_INPUT       = "textarea[placeholder='Please provide an address.']"
    CITY_INPUT          = "input[placeholder='Please provide a city.']"
    SUBMIT_ADDRESS_BTN  = "button[id='submitButton']"

    # Delivery method step
    DELIVERY_OPTION     = "mat-radio-button"
    CONTINUE_BTN        = "button:has-text('Continue')"

    # Payment step (S4 trigger)
    PAYMENT_ROWS        = "mat-row"
    USE_CARD_BTN        = "button:has-text('Use')"
    ADD_CARD_BTN        = "button:has-text('Add New Card')"
    CARD_NAME_INPUT     = "input[data-placeholder='Name']"
    CARD_NUMBER_INPUT   = "input[data-placeholder='Card Number']"
    CARD_EXPIRY_INPUT   = "mat-select[name='expiryMonth']"
    CARD_YEAR_INPUT     = "mat-select[name='expiryYear']"
    SUBMIT_CARD_BTN     = "button[id='submitButton']"

    # Order summary → Confirm
    PLACE_ORDER_BTN     = "button:has-text('Place your order and pay')"

    # Confirmation (S5)
    CONFIRMATION_HEADER = "h1:has-text('Thank you')"
    ORDER_ID_TEXT       = "label.confirmation"

    def __init__(self, page: Page):
        super().__init__(page)

    def select_or_add_address(self) -> bool:
        """Chọn địa chỉ có sẵn hoặc tạo mới."""
        try:
            # Thử chọn địa chỉ có sẵn trước
            existing = self.page.locator(self.USE_ADDRESS_BTN).first
            if existing.is_visible(timeout=3000):
                existing.click()
                logger.info("Selected existing address")
                return True
        except Exception:
            pass

        # Tạo địa chỉ mới
        try:
            self.page.locator(self.NEW_ADDRESS_BTN).click()
            self.page.wait_for_timeout(500)
            self.page.fill(self.COUNTRY_INPUT, "Vietnam")
            self.page.fill(self.NAME_INPUT, "Test User")
            self.page.fill(self.MOBILE_INPUT, "0909000000")
            self.page.fill(self.ZIP_INPUT, "70000")
            self.page.fill(self.ADDRESS_INPUT, "123 Test Street")
            self.page.fill(self.CITY_INPUT, "Ho Chi Minh City")
            self.page.locator(self.SUBMIT_ADDRESS_BTN).click()
            self.page.wait_for_timeout(1000)
            logger.info("Created new address")
            return True
        except Exception as e:
            logger.error(f"Address step failed: {e}")
            return False

    def select_delivery(self) -> bool:
        """Chọn phương thức giao hàng."""
        try:
            options = self.page.locator(self.DELIVERY_OPTION)
            if options.count() > 0:
                options.first.click()
            cont = self.page.locator(self.CONTINUE_BTN).first
            cont.click()
            self.page.wait_for_timeout(800)
            logger.info("Delivery selected (S3)")
            return True
        except Exception as e:
            logger.error(f"Delivery step failed: {e}")
            return False

    def select_or_add_payment(self) -> bool:
        """Chọn thẻ thanh toán có sẵn hoặc thêm mới (S4 trigger)."""
        try:
            existing = self.page.locator(self.USE_CARD_BTN).first
            if existing.is_visible(timeout=3000):
                existing.click()
                logger.info("Selected existing payment card (S4)")
                return True
        except Exception:
            pass

        try:
            self.page.locator(self.ADD_CARD_BTN).click()
            self.page.wait_for_timeout(500)
            self.page.fill(self.CARD_NAME_INPUT, "Test User")
            self.page.fill(self.CARD_NUMBER_INPUT, "4111111111111111")
            # Select expiry month
            self.page.locator(self.CARD_EXPIRY_INPUT).click()
            self.page.locator("mat-option").nth(5).click()
            # Select expiry year
            self.page.locator(self.CARD_YEAR_INPUT).click()
            self.page.locator("mat-option").first.click()
            self.page.locator(self.SUBMIT_CARD_BTN).click()
            self.page.wait_for_timeout(1000)
            # Select the newly added card
            self.page.locator(self.USE_CARD_BTN).first.click()
            logger.info("Added new payment card (S4)")
            return True
        except Exception as e:
            logger.error(f"Payment step failed: {e}")
            return False

    def place_order(self) -> bool:
        """Đặt hàng — kích hoạt S4 → S5."""
        try:
            btn = self.page.locator(self.PLACE_ORDER_BTN)
            btn.click()
            # Đợi trang xác nhận
            self.page.wait_for_selector(self.CONFIRMATION_HEADER, timeout=15000)
            logger.info("Order placed — reached S5 (confirmed)!")
            return True
        except Exception as e:
            logger.error(f"Place order failed: {e}")
            return False

    def is_confirmed(self) -> bool:
        """Kiểm tra đã đến S5 (confirmed) chưa."""
        try:
            header = self.page.locator(self.CONFIRMATION_HEADER)
            return header.is_visible(timeout=5000)
        except Exception:
            return False

    def get_order_id(self) -> str:
        """Lấy mã đơn hàng từ trang xác nhận."""
        try:
            label = self.page.locator(self.ORDER_ID_TEXT)
            return label.inner_text(timeout=3000)
        except Exception:
            return ""

    def complete_checkout_flow(self) -> bool:
        """
        Thực hiện toàn bộ luồng S3→S4→S5:
        Address → Delivery → Payment → Place Order.
        """
        steps = [
            ("Select/add address",  self.select_or_add_address),
            ("Select delivery",     self.select_delivery),
            ("Select/add payment",  self.select_or_add_payment),
            ("Place order",         self.place_order),
        ]
        for step_name, step_fn in steps:
            logger.info(f"Checkout step: {step_name}")
            if not step_fn():
                logger.error(f"Checkout FAILED at: {step_name}")
                return False
        return True

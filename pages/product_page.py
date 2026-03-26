"""
pages/product_page.py
=====================
Fixed v3:
- get_cart_count dùng /api/Baskets/{bid} (đúng endpoint Juice Shop v14+)
- Thêm fallback: check snackbar text và basket route
"""
from playwright.sync_api import Page
from pages.base_page import BasePage
import logging

logger = logging.getLogger(__name__)


class ProductPage(BasePage):
    ADD_TO_CART_SELECTORS = [
        "button[aria-label='Add to Basket']",
        "button[aria-label*='Add']",
        "mat-card button.mat-icon-button",
        "button.mat-mini-fab",
    ]
    PRODUCT_CARDS = "mat-card, .mat-card"
    SUCCESS_SNACK = "simple-snack-bar"

    def __init__(self, page: Page):
        super().__init__(page)

    def open(self):
        self.navigate("#/search")
        self.page.wait_for_selector(self.PRODUCT_CARDS, timeout=10000)
        self.page.wait_for_timeout(1500)
        logger.info("ProductPage opened")

    def add_first_product_to_cart(self) -> bool:
        """Thêm sản phẩm đầu tiên — thử nhiều selector."""
        for sel in self.ADD_TO_CART_SELECTORS:
            try:
                btns = self.page.locator(sel)
                if btns.count() > 0:
                    btns.first.scroll_into_view_if_needed()
                    btns.first.click()
                    try:
                        self.page.locator(self.SUCCESS_SNACK).wait_for(
                            state="visible", timeout=4000
                        )
                    except Exception:
                        self.page.wait_for_timeout(1500)
                    logger.info(f"Added product via selector: {sel}")
                    return True
            except Exception:
                continue
        logger.error("Add to cart FAILED")
        return False

    def get_cart_count(self) -> int:
        """
        Đọc số item qua Juice Shop API.
        Juice Shop v14: GET /api/Baskets/{bid}  →  data.Products.length
        """
        return self._get_cart_count_api()

    def _get_cart_count_api(self) -> int:
        """
        Gọi /api/Baskets/{bid} — endpoint chính xác của Juice Shop.
        Trả về số Products trong basket.
        """
        try:
            result = self.page.evaluate("""async () => {
                const token = localStorage.getItem('token');
                const bid   = localStorage.getItem('bid');
                if (!token || !bid) return -1;
                try {
                    const r = await fetch('/api/Baskets/' + bid, {
                        headers: { 'Authorization': 'Bearer ' + token }
                    });
                    if (!r.ok) return -2;
                    const d = await r.json();
                    // Juice Shop v14 structure: {data: {Products: [...]}}
                    if (d.data && d.data.Products) return d.data.Products.length;
                    // Fallback: BasketItems
                    if (d.data && d.data.BasketItems) return d.data.BasketItems.length;
                    return -3;
                } catch(e) { return -4; }
            }""")
            logger.info(f"Cart API result: {result}")
            return max(0, int(result))
        except Exception as e:
            logger.error(f"Cart API error: {e}")
            return 0

    def get_bid_from_storage(self) -> str:
        """Debug helper: lấy bid từ localStorage."""
        try:
            return self.page.evaluate("""() => {
                const keys = ['bid', 'basketId', 'basket_id'];
                for (const k of keys) {
                    const v = localStorage.getItem(k);
                    if (v) return k + '=' + v;
                }
                return 'NOT_FOUND';
            }""")
        except Exception:
            return "ERROR"


class CartPage(BasePage):
    # Juice Shop basket page selectors — nhiều version khác nhau
    CART_ICON_SELECTORS = [
        "button[aria-label='Show the shopping cart']",
        "button[routerlink='/basket']",
        "mat-icon:has-text('shopping_cart')",
    ]
    CHECKOUT_BTN_SELECTORS = [
        "button[aria-label='Proceed to checkout']",
        "button.mat-raised-button:has-text('Checkout')",
        "button:has-text('Checkout')",
        "#checkoutButton",
    ]
    CART_ITEM_ROWS = "mat-row, .mat-row"
    REMOVE_BTN     = "button[aria-label='Remove from basket']"

    def __init__(self, page: Page):
        super().__init__(page)

    def open(self):
        """Mở basket — navigate trực tiếp thay vì click icon."""
        self.navigate("#/basket")
        self.page.wait_for_timeout(2000)
        logger.info("CartPage opened")

    def get_item_count(self) -> int:
        try:
            # Thử mat-row trước
            rows = self.page.locator("mat-row")
            c = rows.count()
            if c > 0:
                return c
            # Fallback: đếm remove buttons
            return self.page.locator(self.REMOVE_BTN).count()
        except Exception:
            return 0

    def is_empty(self) -> bool:
        return self.get_item_count() == 0

    def proceed_to_checkout(self) -> bool:
        """
        Click checkout — thử nhiều selector vì aria-label thay đổi theo version.
        """
        if self.is_empty():
            logger.warning("Cart empty — cannot checkout")
            return False

        for sel in self.CHECKOUT_BTN_SELECTORS:
            try:
                btn = self.page.locator(sel).first
                if btn.is_visible(timeout=3000):
                    btn.click()
                    try:
                        self.page.wait_for_url("**/#/address**", timeout=8000)
                        logger.info(f"Checkout OK via: {sel}")
                        return True
                    except Exception:
                        # Có thể redirect sang page khác
                        if "#/address" in self.page.url or "#/checkout" in self.page.url:
                            return True
            except Exception:
                continue

        # Last resort: lấy tất cả buttons và in ra để debug
        btns = self.page.evaluate("""() =>
            Array.from(document.querySelectorAll('button')).map(b => ({
                text: b.innerText.trim(),
                aria: b.getAttribute('aria-label') || ''
            })).filter(b => b.text || b.aria)
        """)
        logger.error(f"Checkout button not found. Available buttons: {btns[:10]}")
        return False

    def remove_all_items(self):
        try:
            for _ in range(20):
                btns = self.page.locator(self.REMOVE_BTN)
                if btns.count() == 0:
                    break
                btns.first.click()
                self.page.wait_for_timeout(600)
        except Exception as e:
            logger.warning(f"Remove items: {e}")

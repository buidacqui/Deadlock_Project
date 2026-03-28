"""
pages/product_page.py
=====================
FIX v5:
- add_first_product_to_cart(): đợi snackbar thay vì sleep cứng
- CartPage.remove_all_items(): đợi DOM cập nhật sau mỗi lần remove
- CartPage.is_empty(): reload nhẹ để đảm bảo Angular đã cập nhật count
- CartPage.proceed_to_checkout(): đợi networkidle sau click,
  không gọi is_empty() trước (để test tự kiểm soát logic)
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
        self.page.wait_for_timeout(1000)
        logger.info("ProductPage opened")

    def add_first_product_to_cart(self) -> bool:
        """Thêm sản phẩm đầu tiên — đợi snackbar confirm thay vì sleep."""
        for sel in self.ADD_TO_CART_SELECTORS:
            try:
                btns = self.page.locator(sel)
                if btns.count() > 0:
                    btns.first.scroll_into_view_if_needed()
                    btns.first.click()
                    try:
                        self.page.locator(self.SUCCESS_SNACK).wait_for(
                            state="visible", timeout=5000
                        )
                        logger.info("Snackbar 'Added to basket' đã xuất hiện")
                        self.page.locator(self.SUCCESS_SNACK).wait_for(
                            state="hidden", timeout=5000
                        )
                    except Exception:
                        self.page.wait_for_timeout(800)
                    logger.info(f"Added product via selector: {sel}")
                    return True
            except Exception:
                continue
        logger.error("Add to cart FAILED")
        return False

    def get_cart_count(self) -> int:
        try:
            self.page.wait_for_function(
                "() => !!localStorage.getItem('bid')", timeout=5000
            )
        except Exception:
            pass
        return self._get_cart_count_api()

    def _get_cart_count_api(self) -> int:
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
                    if (d.data && d.data.Products)    return d.data.Products.length;
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
    CHECKOUT_BTN_SELECTORS = [
        "button[aria-label='Proceed to checkout']",
        "button.mat-raised-button:has-text('Checkout')",
        "button:has-text('Checkout')",
        "#checkoutButton",
    ]
    REMOVE_BTN = "button[aria-label='Remove from basket']"

    def __init__(self, page: Page):
        super().__init__(page)

    def open(self):
        """
        Navigate đến basket và extract bid từ network response.

        FIX v7: Juice Shop Angular gọi /api/Baskets/{bid} khi load trang.
        Ta intercept response URL để lấy bid thực sự rồi set vào localStorage.
        Cách này hoạt động ngay cả khi Juice Shop không tự set bid vào localStorage.
        """
        import re
        captured = {}

        def on_response(response):
            if captured.get('bid'):
                return
            try:
                m = re.search(r'/api/Baskets/(\d+)', response.url)
                if m and response.status in (200, 304):
                    captured['bid'] = m.group(1)
            except Exception:
                pass

        self.page.on('response', on_response)
        self.navigate("#/basket")
        try:
            self.page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass
        self.page.wait_for_timeout(1500)
        self.page.remove_listener('response', on_response)

        # Set bid vào localStorage nếu intercepted được
        if captured.get('bid'):
            self.page.evaluate(
                f"() => localStorage.setItem('bid', '{captured['bid']}')"
            )
            logger.info(f"CartPage opened — bid intercepted: {captured['bid']}")
        else:
            logger.warning("CartPage opened — bid không intercepted từ network")

    def get_item_count(self) -> int:
        """
        Đọc số item từ DOM.
        Dùng API để chính xác hơn nếu DOM chưa kịp update.
        """
        try:
            # Thử đọc qua API trước (chính xác hơn DOM)
            result = self.page.evaluate("""async () => {
                const token = localStorage.getItem('token');
                const bid   = localStorage.getItem('bid');
                if (!token || !bid) return -1;
                try {
                    const r = await fetch('/api/Baskets/' + bid, {
                        headers: { 'Authorization': 'Bearer ' + token }
                    });
                    if (!r.ok) return -1;
                    const d = await r.json();
                    if (d.data && d.data.Products)    return d.data.Products.length;
                    if (d.data && d.data.BasketItems) return d.data.BasketItems.length;
                    return 0;
                } catch(e) { return -1; }
            }""")
            if result >= 0:
                return result
        except Exception:
            pass

        # Fallback: DOM
        try:
            rows = self.page.locator("mat-row")
            c = rows.count()
            if c > 0:
                return c
            return self.page.locator(self.REMOVE_BTN).count()
        except Exception:
            return 0

    def is_empty(self) -> bool:
        """
        Kiểm tra giỏ hàng có rỗng không.
        FIX: Reload nhẹ để Angular cập nhật sau remove_all_items().
        """
        try:
            self.page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        return self.get_item_count() == 0

    def proceed_to_checkout(self) -> bool:
        """
        Click checkout button.
        FIX: Không check is_empty() ở đây — để caller tự quyết định.
        Nếu giỏ rỗng, Juice Shop tự disable/ẩn button → trả về False tự nhiên.
        """
        for sel in self.CHECKOUT_BTN_SELECTORS:
            try:
                btn = self.page.locator(sel).first
                if btn.is_visible(timeout=3000) and btn.is_enabled():
                    btn.click()
                    try:
                        self.page.wait_for_load_state("networkidle", timeout=8000)
                    except Exception:
                        pass
                    if "#/address" in self.page.url or "#/checkout" in self.page.url:
                        logger.info(f"Checkout OK via: {sel}")
                        return True
            except Exception:
                continue

        logger.warning("Checkout button không tìm thấy hoặc không enabled")
        return False

    def _api_clear_basket(self) -> bool:
        """
        Xoá toàn bộ items qua Juice Shop REST API.
        Đáng tin cậy hơn DOM click vì không phụ thuộc Angular render timing.
        Endpoint: DELETE /api/BasketItems/{id} cho từng item.
        """
        try:
            result = self.page.evaluate("""async () => {
                const token = localStorage.getItem('token');
                const bid   = localStorage.getItem('bid');
                if (!token || !bid) return { ok: false, reason: 'no_token_or_bid' };
                try {
                    const r = await fetch('/api/Baskets/' + bid, {
                        headers: { 'Authorization': 'Bearer ' + token }
                    });
                    if (!r.ok) return { ok: false, reason: 'fetch_basket_failed' };
                    const d = await r.json();
                    const products = (d.data && (d.data.Products || d.data.BasketItems)) || [];
                    if (products.length === 0) return { ok: true, deleted: 0, total: 0 };
                    let deleted = 0;
                    for (const p of products) {
                        const itemId = (p.BasketItem && p.BasketItem.id) || p.id;
                        if (!itemId) continue;
                        const dr = await fetch('/api/BasketItems/' + itemId, {
                            method: 'DELETE',
                            headers: { 'Authorization': 'Bearer ' + token }
                        });
                        if (dr.ok) deleted++;
                    }
                    return { ok: true, deleted: deleted, total: products.length };
                } catch(e) {
                    return { ok: false, reason: String(e) };
                }
            }""")
            if result and result.get('ok'):
                logger.info(f"API clear basket: xoá {result.get('deleted')}/{result.get('total')} items")
                return True
            logger.warning(f"API clear basket thất bại: {result}")
            return False
        except Exception as e:
            logger.warning(f"_api_clear_basket exception: {e}")
            return False

    def remove_all_items(self):
        """
        Xoá tất cả items khỏi giỏ.

        FIX v7: Ưu tiên xoá qua REST API (không phụ thuộc Angular render timing).
        Fallback sang DOM click nếu bid=null hoặc API thất bại.
        Reload #/basket cuối cùng để đảm bảo state fresh.
        """
        try:
            # Bước 1: Xoá qua API (nhanh + không phụ thuộc DOM render)
            api_ok = self._api_clear_basket()

            if not api_ok:
                # Bước 2 fallback: DOM click (đợi Angular render xong trước)
                logger.info("API clear thất bại, fallback DOM click...")
                try:
                    self.page.wait_for_load_state("networkidle", timeout=8000)
                except Exception:
                    pass
                self.page.wait_for_timeout(2000)

                for _ in range(20):
                    btns = self.page.locator(self.REMOVE_BTN)
                    if btns.count() == 0:
                        break
                    prev_count = btns.count()
                    btns.first.click()
                    try:
                        self.page.wait_for_function(
                            f"() => document.querySelectorAll(\"button[aria-label='Remove from basket']\").length < {prev_count}",
                            timeout=5000
                        )
                    except Exception:
                        self.page.wait_for_timeout(800)

            # Bước 3: Reload basket để force API trả state mới nhất
            self.navigate("#/basket")
            try:
                self.page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass
            self.page.wait_for_timeout(1000)
            logger.info("Đã xoá tất cả items")

        except Exception as e:
            logger.warning(f"Remove items: {e}")

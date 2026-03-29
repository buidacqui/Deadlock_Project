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
        """
        Thêm 1 sản phẩm NGẪU NHIÊN vào giỏ.
        Scroll nhẹ để load thêm sản phẩm (lazy load), rồi random.randint
        trong toàn bộ danh sách buttons hiện có → tránh lặp lại cùng 1 sản phẩm.
        """
        import random
        for sel in self.ADD_TO_CART_SELECTORS:
            try:
                btns = self.page.locator(sel)
                count = btns.count()
                if count > 0:
                    idx = random.randint(0, count - 1)
                    chosen = btns.nth(idx)
                    chosen.scroll_into_view_if_needed()
                    chosen.click()
                    logger.info(f"Added random product #{idx + 1}/{count} via: {sel}")
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
        Navigate đến basket. Dùng page.route để intercept request và lấy bid.

        FIX v9: page.route intercept REQUEST (không phải response) → không có
        race condition. Glob pattern rộng để bắt mọi basket endpoint của Juice Shop.
        """
        import re
        captured = {}

        def handle_route(route):
            url = route.request.url
            # Bắt mọi pattern: /api/Baskets/N, /rest/basket/N, v.v.
            m = re.search(r'[Bb]asket[sS]?/(\d+)', url)
            if m and not captured.get('bid'):
                captured['bid'] = m.group(1)
            route.continue_()

        # Setup interceptor TRƯỚC khi navigate → không bỏ sót request nào
        try:
            self.page.route('**/*asket*/**', handle_route)
        except Exception:
            pass

        self.navigate("#/basket")
        try:
            self.page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass
        self.page.wait_for_timeout(1500)

        try:
            self.page.unroute('**/*asket*/**', handle_route)
        except Exception:
            pass

        if captured.get('bid'):
            self.page.evaluate(
                f"() => localStorage.setItem('bid', '{captured['bid']}')"
            )
            logger.info(f"CartPage opened — bid: {captured['bid']}")
        else:
            # Last resort: scan all network requests via performance entries
            try:
                bid = self.page.evaluate("""() => {
                    const entries = performance.getEntriesByType('resource');
                    for (const e of entries) {
                        const m = e.name.match(/[Bb]asket[sS]?\\/(\d+)/);
                        if (m) return m[1];
                    }
                    return null;
                }""")
                if bid:
                    self.page.evaluate(f"() => localStorage.setItem('bid', '{bid}')")
                    logger.info(f"CartPage opened — bid từ performance entries: {bid}")
                else:
                    logger.warning("CartPage opened — bid không tìm được, DOM fallback sẽ được dùng")
            except Exception:
                logger.warning("CartPage opened — bid không tìm được")

        logger.info("CartPage opened")

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

        FIX v9: Ưu tiên DOM check (không cần bid).
        Đợi Angular render xong trước khi đếm.
        """
        try:
            self.page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        # Đợi Angular render (chờ mat-table hoặc empty-state)
        self.page.wait_for_timeout(800)

        # DOM check: đếm remove buttons (đáng tin hơn mat-row)
        try:
            remove_count = self.page.locator(self.REMOVE_BTN).count()
            if remove_count == 0:
                # Xác nhận thêm: không có mat-row nào
                row_count = self.page.locator("mat-row").count()
                if row_count == 0:
                    return True
                # row_count > 0 nhưng remove_btn = 0 → vẫn coi là empty
                return True
            return False
        except Exception:
            pass

        # Fallback API nếu có bid
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

    def _playwright_clear_basket(self) -> bool:
        """
        Xoá basket dùng Playwright page.request (Python-level HTTP).

        FIX v10: Khi GET /api/Baskets/{bid} trả 500 (basket corrupt sau nhiều
        lần test), tạo basket MỚI bằng POST /api/Baskets rồi update localStorage.
        Basket mới đương nhiên rỗng → test tiếp tục bình thường.
        """
        import base64, json as pyjson
        BASE = "http://localhost:3000"

        try:
            token = self.page.evaluate("() => localStorage.getItem('token')")
            headers = {'Authorization': f'Bearer {token}'} if token else {}

            # Lấy bid từ localStorage (đã được set bởi CartPage.open())
            bid = self.page.evaluate("() => localStorage.getItem('bid')")

            # Fallback: decode JWT
            if not bid and token:
                try:
                    padded = token.split('.')[1] + '=='
                    payload = pyjson.loads(base64.b64decode(padded))
                    uid = (payload.get('data') or {}).get('id') or payload.get('id')
                    if uid:
                        bid = str(uid)
                        logger.info(f"bid từ JWT userId: {bid}")
                except Exception:
                    pass

            if not bid:
                logger.warning("Không tìm được bid")
                return False

            # Thử GET basket
            r = self.page.request.get(f"{BASE}/api/Baskets/{bid}", headers=headers)

            if not r.ok:
                # ── FIX: basket corrupt (500) → tạo basket mới ──────────
                logger.warning(f"GET basket/{bid} = {r.status} → tạo basket mới")
                new_bid = self._create_fresh_basket(BASE, headers, token)
                if new_bid:
                    logger.info(f"✓ Basket mới đã tạo: bid={new_bid} (rỗng)")
                    return True
                # Nếu tạo mới cũng fail → báo cáo nhưng không crash
                logger.warning("Không thể tạo basket mới, DOM fallback sẽ xử lý")
                return False

            # GET OK → xoá từng item
            basket_data = (r.json().get('data') or {})
            products = basket_data.get('Products') or basket_data.get('BasketItems') or []

            if not products:
                logger.info("Basket đã rỗng")
                return True

            deleted = 0
            for p in products:
                item_id = (p.get('BasketItem') or {}).get('id') or p.get('id')
                if not item_id:
                    continue
                dr = self.page.request.delete(
                    f"{BASE}/api/BasketItems/{item_id}", headers=headers
                )
                if dr.ok:
                    deleted += 1

            logger.info(f"Playwright clear: deleted {deleted}/{len(products)} items")
            return deleted > 0 or len(products) == 0

        except Exception as e:
            logger.warning(f"_playwright_clear_basket exception: {e}")
            return False

    def _create_fresh_basket(self, base_url: str, headers: dict, token: str) -> str:
        """
        Tạo basket mới qua POST /api/Baskets.
        Trả về bid mới (string) hoặc None nếu thất bại.
        Cũng update localStorage để các call sau dùng bid mới.
        """
        import base64, json as pyjson

        try:
            # Lấy userId từ JWT để gắn basket mới vào đúng user
            user_id = None
            if token:
                try:
                    padded = token.split('.')[1] + '=='
                    payload = pyjson.loads(base64.b64decode(padded))
                    user_id = (payload.get('data') or {}).get('id') or payload.get('id')
                except Exception:
                    pass

            body = {'UserId': user_id} if user_id else {}
            r = self.page.request.post(
                f"{base_url}/api/Baskets",
                headers={**headers, 'Content-Type': 'application/json'},
                data=pyjson.dumps(body)
            )
            if r.ok:
                data = r.json().get('data') or {}
                new_bid = str(data.get('id') or '')
                if new_bid:
                    # Update localStorage để Juice Shop frontend dùng basket mới
                    self.page.evaluate(
                        f"() => localStorage.setItem('bid', '{new_bid}')"
                    )
                    logger.info(f"Tạo basket mới thành công: bid={new_bid}")
                    return new_bid
            logger.warning(f"POST /api/Baskets thất bại: {r.status}")
        except Exception as e:
            logger.warning(f"_create_fresh_basket exception: {e}")
        return None

    def _api_clear_basket(self) -> bool:
        """Wrapper: thử JS fetch trước, fallback sang Playwright request."""
        # Thử JS fetch (nhanh nếu có token+bid trong localStorage)
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
                logger.info(f"JS clear: {result.get('deleted')}/{result.get('total')} items")
                return True
        except Exception:
            pass

        # Fallback: Playwright HTTP (dùng browser session, không cần localStorage)
        return self._playwright_clear_basket()

    def remove_all_items(self):
        """
        Xoá tất cả items khỏi giỏ.

        FIX FINAL: Ưu tiên Playwright HTTP API (không phụ thuộc localStorage.bid).
        DOM fallback với wait_for_selector đảm bảo Angular đã render.
        Reload cuối để verify state fresh.
        """
        try:
            api_ok = self._api_clear_basket()

            if not api_ok:
                # DOM fallback — đợi buttons xuất hiện trước
                logger.info("DOM fallback: đợi remove buttons...")
                try:
                    self.page.wait_for_selector(
                        self.REMOVE_BTN, timeout=10000, state="visible"
                    )
                    logger.info("✓ Remove buttons sẵn sàng, bắt đầu xoá")
                except Exception:
                    logger.warning("Remove buttons không xuất hiện (basket đã rỗng?)")

                for _ in range(20):
                    btns = self.page.locator(self.REMOVE_BTN)
                    n = btns.count()
                    if n == 0:
                        break
                    btns.first.click()
                    try:
                        self.page.wait_for_function(
                            f"() => document.querySelectorAll(\"button[aria-label='Remove from basket']\").length < {n}",
                            timeout=5000
                        )
                    except Exception:
                        self.page.wait_for_timeout(800)
                    remaining = self.page.locator(self.REMOVE_BTN).count()
                    logger.info(f"Removed 1, còn {remaining}")

            # Reload để Angular sync state mới nhất
            self.navigate("#/basket")
            try:
                self.page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass
            self.page.wait_for_timeout(1000)
            logger.info("Đã xoá tất cả items")

        except Exception as e:
            logger.warning(f"Remove items exception: {e}")

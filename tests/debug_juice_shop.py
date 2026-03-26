"""
tests/debug_juice_shop.py
=========================
Script debug selectors thực tế của Juice Shop.
Chạy: pytest tests/debug_juice_shop.py -m ui -v --headed -s
"""
import pytest
import json

BASE_URL   = "http://localhost:3000"
VALID_USER = "admin@juice-sh.op"
VALID_PASS = "admin123"


@pytest.mark.ui
def test_debug_login_and_localstorage(page):
    """In ra toàn bộ localStorage sau khi login."""
    page.goto(f"{BASE_URL}/#/login", wait_until="networkidle")

    # Dismiss dialogs
    for sel in ["button[aria-label='Close Welcome Banner']", "mat-dialog-container button"]:
        try:
            if page.locator(sel).first.is_visible(timeout=1000):
                page.locator(sel).first.click()
        except Exception:
            pass

    page.wait_for_selector("#email", timeout=8000)
    page.fill("#email", VALID_USER)
    page.fill("#password", VALID_PASS)
    page.click("#loginButton")

    try:
        page.wait_for_function("() => !!localStorage.getItem('token')", timeout=7000)
        print("\n✓ Login SUCCESS")
    except Exception:
        print("\n✗ Login FAILED")

    # Dump toàn bộ localStorage
    storage = page.evaluate("""() => {
        const result = {};
        for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            result[key] = localStorage.getItem(key);
        }
        return result;
    }""")
    print("\n=== localStorage keys after login ===")
    for k, v in storage.items():
        val = v[:80] if len(str(v)) > 80 else v
        print(f"  {k}: {val}")


@pytest.mark.ui
def test_debug_add_to_cart_and_storage(page):
    """Debug: sau khi add to cart, localStorage chứa gì."""
    # Login
    page.goto(f"{BASE_URL}/#/login", wait_until="networkidle")
    for sel in ["button[aria-label='Close Welcome Banner']", "mat-dialog-container button"]:
        try:
            if page.locator(sel).first.is_visible(timeout=1000):
                page.locator(sel).first.click()
        except Exception:
            pass
    page.fill("#email", VALID_USER)
    page.fill("#password", VALID_PASS)
    page.click("#loginButton")
    page.wait_for_function("() => !!localStorage.getItem('token')", timeout=7000)
    print("\n✓ Login OK")

    # Go to search
    page.goto(f"{BASE_URL}/#/search", wait_until="networkidle")
    page.wait_for_timeout(2000)

    # In ra các add-to-cart buttons
    for sel in [
        "button[aria-label='Add to Basket']",
        "button[aria-label*='Add']",
        "button[aria-label*='Basket']",
        "mat-card button",
    ]:
        count = page.locator(sel).count()
        print(f"  Selector '{sel}': {count} buttons")

    # Click add to cart
    added = False
    for sel in ["button[aria-label='Add to Basket']", "button[aria-label*='Add']"]:
        try:
            btns = page.locator(sel)
            if btns.count() > 0:
                btns.first.click()
                page.wait_for_timeout(2000)
                added = True
                print(f"\n✓ Clicked add button: {sel}")
                break
        except Exception as e:
            print(f"  Failed {sel}: {e}")

    # Dump localStorage sau khi add
    storage = page.evaluate("""() => {
        const r = {};
        for (let i = 0; i < localStorage.length; i++) {
            const k = localStorage.key(i);
            r[k] = localStorage.getItem(k);
        }
        return r;
    }""")
    print("\n=== localStorage after add to cart ===")
    for k, v in storage.items():
        val = str(v)[:100]
        print(f"  {k}: {val}")

    # Thử gọi API với nhiều key khác nhau
    token = storage.get("token", "")
    print("\n=== Try API calls ===")
    for bid_key in ["bid", "basketId", "basket_id", "cartId"]:
        bid = storage.get(bid_key, "")
        if bid:
            result = page.evaluate(f"""async () => {{
                try {{
                    const r = await fetch('/api/BasketItems?BasketId={bid}', {{
                        headers: {{ 'Authorization': 'Bearer {token}' }}
                    }});
                    const d = await r.json();
                    return JSON.stringify(d).substring(0, 200);
                }} catch(e) {{ return 'ERROR: ' + e.message; }}
            }}""")
            print(f"  bid_key='{bid_key}', bid='{bid}': {result}")


@pytest.mark.ui
def test_debug_basket_page_selectors(page):
    """Debug: selectors trên trang basket."""
    # Login + add item
    page.goto(f"{BASE_URL}/#/login", wait_until="networkidle")
    for sel in ["button[aria-label='Close Welcome Banner']", "mat-dialog-container button"]:
        try:
            if page.locator(sel).first.is_visible(timeout=1000):
                page.locator(sel).first.click()
        except Exception:
            pass
    page.fill("#email", VALID_USER)
    page.fill("#password", VALID_PASS)
    page.click("#loginButton")
    page.wait_for_function("() => !!localStorage.getItem('token')", timeout=7000)

    page.goto(f"{BASE_URL}/#/search", wait_until="networkidle")
    page.wait_for_timeout(1500)
    for sel in ["button[aria-label='Add to Basket']", "button[aria-label*='Add']"]:
        try:
            if page.locator(sel).count() > 0:
                page.locator(sel).first.click()
                page.wait_for_timeout(1500)
                break
        except Exception:
            pass

    # Navigate to basket
    page.goto(f"{BASE_URL}/#/basket", wait_until="networkidle")
    page.wait_for_timeout(2000)
    print(f"\n=== Current URL: {page.url}")
    print(f"=== Page title: {page.title()}")

    # In ra tất cả buttons trên trang
    buttons = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('button')).map(b => ({
            text: b.innerText.trim().substring(0, 50),
            ariaLabel: b.getAttribute('aria-label') || '',
            id: b.id || '',
            class: b.className.substring(0, 60)
        }));
    }""")
    print("\n=== All buttons on basket page ===")
    for b in buttons:
        if b['text'] or b['ariaLabel']:
            print(f"  text='{b['text']}' | aria='{b['ariaLabel']}' | id='{b['id']}'")

"""
pages/base_page.py
==================
BasePage — Page Object Model base class cho Playwright.

FIX v2:
- navigate(): thêm wait_for_load_state("networkidle") sau goto()
  để Angular SPA có thời gian bootstrapping trước khi test tiếp
- _dismiss_dialogs(): tăng timeout lên 2000ms, thêm wait sau click
- Thêm wait_for_angular(): đợi Angular zone stable (hữu ích cho Juice Shop)
"""
from playwright.sync_api import Page
import logging

logger = logging.getLogger(__name__)


class BasePage:
    BASE_URL = "http://localhost:3000"

    def __init__(self, page: Page):
        self.page = page

    def navigate(self, path: str = ""):
        """
        Navigate tới URL và đợi Angular SPA render xong.

        FIX: Thêm wait_for_load_state("networkidle") thay vì chỉ goto().
        Juice Shop là Angular SPA — sau khi URL thay đổi, Angular vẫn
        cần thêm thời gian để render component. Không đợi → các selector
        sau chưa tồn tại → test "nhảy liên tục".
        """
        url = f"{self.BASE_URL}/{path}".rstrip("/")
        logger.info(f"Navigate → {url}")
        self.page.goto(url, wait_until="domcontentloaded")

        # Đợi networkidle: đảm bảo Angular đã fetch xong data
        try:
            self.page.wait_for_load_state("networkidle", timeout=12000)
        except Exception:
            # networkidle có thể timeout ở trang có polling — không fail test
            pass

        # Đợi thêm một tick nhỏ cho Angular zone
        self.page.wait_for_timeout(300)

        self._dismiss_dialogs()

    def _dismiss_dialogs(self):
        """
        Đóng welcome banner và cookie consent của Juice Shop.

        FIX: Tăng timeout lên 2000ms và thêm wait sau mỗi click
        để tránh tình trạng dialog đóng chưa xong mà code đã tiếp tục.
        """
        selectors = [
            "button[aria-label='Close Welcome Banner']",
            "button.mat-focus-indicator:has-text('Dismiss')",
            ".cdk-overlay-container button.mat-button:has-text('Me want it!')",
            "mat-dialog-container button",
        ]
        for sel in selectors:
            try:
                btn = self.page.locator(sel).first
                if btn.is_visible(timeout=2000):
                    btn.click()
                    # Đợi dialog animation đóng xong
                    self.page.wait_for_timeout(400)
            except Exception:
                pass

    def wait_for_angular(self, timeout: int = 8000):
        """
        Đợi Angular zone stable bằng cách poll cho đến khi
        document.readyState = 'complete' và không còn pending request.
        Hữu ích sau khi click button triggering navigation.
        """
        try:
            self.page.wait_for_load_state("networkidle", timeout=timeout)
        except Exception:
            pass

    def get_current_url(self) -> str:
        return self.page.url

    def wait_for_url(self, pattern: str, timeout: int = 10000):
        self.page.wait_for_url(f"**{pattern}**", timeout=timeout)

    def take_screenshot(self, name: str):
        import os
        path = f"reports/screenshots/{name}.png"
        os.makedirs("reports/screenshots", exist_ok=True)
        self.page.screenshot(path=path)
        logger.info(f"Screenshot: {path}")
        return path

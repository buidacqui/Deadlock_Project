"""
pages/base_page.py
==================
BasePage — Page Object Model base class cho Playwright.
Tất cả page objects kế thừa từ class này.
"""
from playwright.sync_api import Page, expect
import logging

logger = logging.getLogger(__name__)


class BasePage:
    BASE_URL = "http://localhost:3000"

    def __init__(self, page: Page):
        self.page = page

    def navigate(self, path: str = ""):
        url = f"{self.BASE_URL}/{path}".rstrip("/")
        logger.info(f"Navigate → {url}")
        self.page.goto(url, wait_until="networkidle")
        self._dismiss_dialogs()

    def _dismiss_dialogs(self):
        """Đóng welcome banner và cookie consent của Juice Shop."""
        selectors = [
            "button[aria-label='Close Welcome Banner']",
            "button.mat-focus-indicator:has-text('Dismiss')",
            ".cdk-overlay-container button.mat-button:has-text('Me want it!')",
            "mat-dialog-container button",
        ]
        for sel in selectors:
            try:
                btn = self.page.locator(sel).first
                if btn.is_visible(timeout=1500):
                    btn.click()
                    self.page.wait_for_timeout(300)
            except Exception:
                pass

    def get_current_url(self) -> str:
        return self.page.url

    def wait_for_url(self, pattern: str, timeout: int = 10000):
        self.page.wait_for_url(f"**{pattern}**", timeout=timeout)

    def take_screenshot(self, name: str):
        path = f"reports/screenshots/{name}.png"
        import os; os.makedirs("reports/screenshots", exist_ok=True)
        self.page.screenshot(path=path)
        logger.info(f"Screenshot: {path}")
        return path

"""
pages/login_page.py
===================
Page Object cho trang Login của OWASP Juice Shop.
Fixed: selector input dùng #email/#password, URL check sau login.
"""
from playwright.sync_api import Page
from pages.base_page import BasePage
import logging

logger = logging.getLogger(__name__)

VALID_EMAIL    = "admin@juice-sh.op"
VALID_PASSWORD = "admin123"


class LoginPage(BasePage):
    # Selectors — Juice Shop thực tế dùng id #email, #password
    EMAIL_INPUT    = "#email"
    PASSWORD_INPUT = "#password"
    LOGIN_BUTTON   = "#loginButton"
    ERROR_SNACK    = "simple-snack-bar"
    MAT_ERROR      = "mat-error"
    NAV_ACCOUNT    = "#navbarAccount"
    LOGOUT_ITEM    = "button[aria-label='Logout']"

    def __init__(self, page: Page):
        super().__init__(page)

    def open(self):
        self.navigate("#/login")
        self.page.wait_for_selector(self.EMAIL_INPUT, timeout=10000)
        logger.info("LoginPage opened")

    def login(self, email: str, password: str) -> bool:
        """
        Đăng nhập. Trả về True nếu thành công.
        Juice Shop redirect về /#/ hoặc /#/search sau login.
        """
        self.page.wait_for_selector(self.EMAIL_INPUT, timeout=8000)
        self.page.fill(self.EMAIL_INPUT, "")
        self.page.type(self.EMAIL_INPUT, email, delay=30)
        self.page.fill(self.PASSWORD_INPUT, "")
        self.page.type(self.PASSWORD_INPUT, password, delay=30)
        self.page.click(self.LOGIN_BUTTON)

        try:
            # Đợi token xuất hiện trong localStorage = login thành công
            self.page.wait_for_function(
                "() => !!localStorage.getItem('token')",
                timeout=6000
            )
            logger.info(f"Login SUCCESS: {email}")
            return True
        except Exception:
            pass

        # Fallback: check URL đã rời login page
        try:
            self.page.wait_for_function(
                "() => !window.location.href.includes('#/login')",
                timeout=3000
            )
            if "token" in (self.page.evaluate("() => localStorage.getItem('token') || ''") or ""):
                logger.info(f"Login SUCCESS (fallback): {email}")
                return True
        except Exception:
            pass

        logger.warning(f"Login FAILED: {email}")
        return False

    def login_valid(self) -> bool:
        """Đăng nhập với tài khoản admin mặc định."""
        return self.login(VALID_EMAIL, VALID_PASSWORD)

    def login_invalid(self, email: str = "wrong@test.com", password: str = "wrongpass") -> bool:
        """Đăng nhập sai — kỳ vọng thất bại."""
        return self.login(email, password)

    def is_logged_in(self) -> bool:
        """Kiểm tra session đang active bằng localStorage token."""
        try:
            token = self.page.evaluate("() => localStorage.getItem('token')")
            return bool(token)
        except Exception:
            return False

    def get_error_message(self) -> str:
        """Lấy thông báo lỗi khi login thất bại."""
        for sel in [self.MAT_ERROR, self.ERROR_SNACK]:
            try:
                el = self.page.locator(sel).first
                if el.is_visible(timeout=2000):
                    return el.inner_text(timeout=2000)
            except Exception:
                continue
        return ""

    def logout(self):
        """Đăng xuất và xóa token."""
        try:
            self.page.locator(self.NAV_ACCOUNT).click(timeout=3000)
            self.page.wait_for_timeout(500)
            self.page.locator(self.LOGOUT_ITEM).click(timeout=3000)
            self.page.wait_for_timeout(800)
            logger.info("Logged out")
        except Exception:
            # Fallback: xóa token trực tiếp
            try:
                self.page.evaluate("() => { localStorage.removeItem('token'); sessionStorage.clear(); }")
                self.navigate("#/login")
            except Exception as e:
                logger.warning(f"Logout fallback error: {e}")

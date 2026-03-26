"""
tests/test_boundary_state.py
============================
Nhóm 3: Boundary State Tests
Kiểm thử các trạng thái biên: session expire, cart rỗng,
login fail, payment fail liên tiếp.
Kỳ vọng: xử lý nhất quán, không deadlock tại boundary.
"""

import pytest
from utils.fsm_engine import OrderWorkflow
from utils.data_loader import DataLoader


loader = DataLoader()
BOUNDARY_CASES = loader.load_sheet("boundary")


@pytest.mark.boundary
@pytest.mark.fsm_only
class TestBoundaryState:
    """
    Nhóm 3: Boundary State Tests
    Các trường hợp tại biên giới hợp lệ/lỗi không được phép gây deadlock.
    """

    @pytest.mark.parametrize("tc", BOUNDARY_CASES, ids=[tc["TC_ID"] for tc in BOUNDARY_CASES])
    def test_boundary_no_deadlock(self, tc, report):
        """
        DDT: Mỗi boundary TC không được dẫn đến deadlock (S6).
        Hệ thống phải xử lý gracefully.
        """
        wf = OrderWorkflow(session_id=tc["TC_ID"])
        events = loader.parse_events(tc["Event_Sequence"])
        wf.apply_events(events)

        # Boundary cases KHÔNG được deadlock
        assert not wf.is_deadlocked(), (
            f"[{tc['TC_ID']}] Boundary case KHÔNG được phép deadlock!\n"
            f"  Events: {tc['Event_Sequence']}\n"
            f"  Path  : {wf.get_path()}"
        )

        assert wf.state == tc["Expected_State"], (
            f"[{tc['TC_ID']}] Trạng thái biên không đúng.\n"
            f"  Expected: {tc['Expected_State']}\n"
            f"  Actual  : {wf.state}\n"
            f"  Path    : {wf.get_path()}"
        )

        report.record(
            tc_id=tc["TC_ID"],
            group="Boundary State",
            description=tc["Description"],
            event_sequence=tc["Event_Sequence"],
            expected_state=tc["Expected_State"],
            actual_state=wf.state,
            expected_result=tc["Expected_Result"],
            actual_result="PASS",
            path_taken=wf.get_path(),
            is_deadlock_expected=False,
        )

    # ─── Unit tests cho từng boundary scenario ──────────────

    def test_session_expire_at_checkout_redirects_to_guest(self):
        """
        S3 → S7 → S0: Session expire tại checkout
        → phải redirect về guest, KHÔNG phải deadlock.
        """
        wf = OrderWorkflow()
        wf.do_login()
        wf.do_add_to_cart()
        wf.do_checkout()
        assert wf.state == "checkout"

        wf.do_session_expire()
        assert wf.state == "expired", f"Expected 'expired', got '{wf.state}'"

        wf.do_restore()
        assert wf.state == "guest", f"Expected 'guest' after restore, got '{wf.state}'"
        assert not wf.is_deadlocked()

    def test_session_expire_at_processing(self):
        """S4 → S7 → S0: Session expire tại payment processing."""
        wf = OrderWorkflow()
        wf.do_login()
        wf.do_add_to_cart()
        wf.do_checkout()
        wf.do_pay()
        assert wf.state == "processing"

        wf.do_session_expire()
        assert wf.state == "expired"
        wf.do_restore()
        assert wf.state == "guest"
        assert not wf.is_deadlocked()

    def test_login_fail_does_not_change_state(self):
        """S0 → S0: Login sai không thay đổi trạng thái (giữ ở guest)."""
        wf = OrderWorkflow()
        wf.do_login_fail()
        assert wf.state == "guest", f"Login fail phải giữ ở guest, got '{wf.state}'"

    def test_multiple_login_fails_then_success(self):
        """Login fail 3 lần → login thành công vẫn hoạt động bình thường."""
        wf = OrderWorkflow()
        for _ in range(3):
            wf.do_login_fail()
            assert wf.state == "guest"
        wf.do_login()
        assert wf.state == "authenticated"
        assert not wf.is_deadlocked()

    def test_empty_cart_boundary(self):
        """Cart rỗng: do_empty_cart giữ ở cart_active (không thể checkout khi rỗng)."""
        wf = OrderWorkflow()
        wf.do_login()
        wf.do_add_to_cart()
        assert wf.state == "cart_active"
        wf.do_empty_cart()
        # Vẫn ở cart_active (boundary — không thể checkout)
        assert wf.state == "cart_active"
        assert not wf.is_deadlocked()

    def test_cancel_checkout_returns_to_cart(self):
        """S3 → S2: do_cancel tại checkout trả về cart_active."""
        wf = OrderWorkflow()
        wf.do_login()
        wf.do_add_to_cart()
        wf.do_checkout()
        wf.do_cancel()
        assert wf.state == "cart_active"
        assert not wf.is_deadlocked()

    def test_cancel_cart_returns_to_authenticated(self):
        """S2 → S1: do_cancel tại cart_active trả về authenticated."""
        wf = OrderWorkflow()
        wf.do_login()
        wf.do_add_to_cart()
        wf.do_cancel()
        assert wf.state == "authenticated"

    def test_payment_fail_and_retry(self):
        """S4 → S3 → S4: payment fail → retry về checkout → pay lại."""
        wf = OrderWorkflow()
        wf.do_login()
        wf.do_add_to_cart()
        wf.do_checkout()
        wf.do_pay()
        wf.do_pay_fail()
        assert wf.state == "checkout"
        assert not wf.is_deadlocked()

    def test_multiple_payment_fails_not_deadlock(self):
        """Payment fail nhiều lần KHÔNG dẫn đến deadlock."""
        wf = OrderWorkflow()
        wf.do_login()
        wf.do_add_to_cart()
        wf.do_checkout()
        for _ in range(5):
            wf.do_pay()
            wf.do_pay_fail()
            assert wf.state == "checkout"
            assert not wf.is_deadlocked()
        # Cuối cùng vẫn hoàn thành được
        wf.do_pay()
        wf.do_confirm()
        assert wf.state == "confirmed"

    def test_session_expire_at_authenticated(self):
        """S1 → S7 → S0: Session expire tại authenticated state."""
        wf = OrderWorkflow()
        wf.do_login()
        wf.do_session_expire()
        assert wf.state == "expired"
        wf.do_restore()
        assert wf.state == "guest"

    def test_boundary_states_not_in_deadlock_history(self):
        """
        Kiểm chứng AG: Lịch sử boundary path KHÔNG chứa 'deadlock'.
        """
        wf = OrderWorkflow()
        # BD_002 scenario: login→add→checkout→expire→restore
        wf.do_login()
        wf.do_add_to_cart()
        wf.do_checkout()
        wf.do_session_expire()
        wf.do_restore()

        assert "deadlock" not in wf.history, (
            f"'deadlock' KHÔNG được xuất hiện trong boundary path!\n"
            f"History: {wf.history}"
        )

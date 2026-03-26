"""
tests/test_valid_path.py
========================
Nhóm 1: Valid Path Tests
Kiểm thử các luồng trạng thái hợp lệ từ S0 → S5 (guest → confirmed).
Kỳ vọng: PASS toàn bộ, không có trạng thái bị chặn.
"""

import pytest
from utils.fsm_engine import OrderWorkflow
from utils.data_loader import DataLoader


# ─── Load test data từ Excel ────────────────────────────────
loader = DataLoader()
VALID_CASES = loader.load_sheet("valid")


# ─── Test class ─────────────────────────────────────────────

@pytest.mark.valid_path
@pytest.mark.fsm_only
class TestValidPath:
    """
    Kiểm thử Group 1: Valid Path
    Thuộc tính: Mọi luồng hợp lệ PHẢI đạt trạng thái 'confirmed' (S5).
    """

    @pytest.mark.parametrize("tc", VALID_CASES, ids=[tc["TC_ID"] for tc in VALID_CASES])
    def test_valid_workflow_reaches_confirmed(self, tc, report):
        """
        DDT: Đọc từng dòng trong sheet Valid_Path và kiểm thử.
        Mỗi TC là một chuỗi sự kiện từ 'guest' → phải kết thúc tại 'confirmed'.
        """
        wf = OrderWorkflow(session_id=tc["TC_ID"])
        events = loader.parse_events(tc["Event_Sequence"])

        # Áp dụng chuỗi sự kiện
        success = wf.apply_events(events)

        # Assertions
        assert success, (
            f"[{tc['TC_ID']}] Event sequence thất bại tại một bước.\n"
            f"  Events: {tc['Event_Sequence']}\n"
            f"  State khi lỗi: {wf.state}\n"
            f"  Path: {wf.get_path()}"
        )

        assert wf.state == tc["Expected_State"], (
            f"[{tc['TC_ID']}] Trạng thái cuối không đúng.\n"
            f"  Expected: {tc['Expected_State']}\n"
            f"  Actual  : {wf.state}\n"
            f"  Path    : {wf.get_path()}"
        )

        assert not wf.is_deadlocked(), (
            f"[{tc['TC_ID']}] KHÔNG được phép có deadlock trong Valid Path!\n"
            f"  Path: {wf.get_path()}"
        )

        assert wf.is_valid_terminal(), (
            f"[{tc['TC_ID']}] Phải kết thúc ở terminal hợp lệ (confirmed).\n"
            f"  Actual state: {wf.state}"
        )

        # Ghi kết quả vào report
        report.record(
            tc_id=tc["TC_ID"],
            group="Valid Path",
            description=tc["Description"],
            event_sequence=tc["Event_Sequence"],
            expected_state=tc["Expected_State"],
            actual_state=wf.state,
            expected_result=tc["Expected_Result"],
            actual_result="PASS",
            path_taken=wf.get_path(),
            is_deadlock_expected=False,
        )

    @pytest.mark.parametrize("tc", VALID_CASES, ids=[tc["TC_ID"] for tc in VALID_CASES])
    def test_no_deadlock_in_valid_path(self, tc, report):
        """Kiểm chứng AG(¬S6): không có deadlock state trong valid path."""
        wf = OrderWorkflow(session_id=f"{tc['TC_ID']}_ag_check")
        events = loader.parse_events(tc["Event_Sequence"])
        wf.apply_events(events)

        # Kiểm tra lịch sử KHÔNG qua trạng thái deadlock
        assert "deadlock" not in wf.history, (
            f"[{tc['TC_ID']}] Phát hiện 'deadlock' trong lịch sử trạng thái!\n"
            f"  Full path: {wf.get_path()}"
        )

    def test_initial_state_is_guest(self):
        """FSM khởi đầu luôn ở trạng thái 'guest' (S0)."""
        wf = OrderWorkflow()
        assert wf.state == "guest", f"Expected 'guest', got '{wf.state}'"

    def test_login_transition(self):
        """S0 → S1: do_login chuyển từ guest sang authenticated."""
        wf = OrderWorkflow()
        wf.do_login()
        assert wf.state == "authenticated"

    def test_add_to_cart_transition(self):
        """S1 → S2: do_add_to_cart chuyển từ authenticated sang cart_active."""
        wf = OrderWorkflow()
        wf.do_login()
        wf.do_add_to_cart()
        assert wf.state == "cart_active"

    def test_multiple_add_to_cart(self):
        """S2 → S2: Thêm nhiều sản phẩm, vẫn ở cart_active."""
        wf = OrderWorkflow()
        wf.do_login()
        wf.do_add_to_cart()
        wf.do_add_to_cart()
        wf.do_add_to_cart()
        assert wf.state == "cart_active"

    def test_checkout_transition(self):
        """S2 → S3: do_checkout chuyển từ cart_active sang checkout."""
        wf = OrderWorkflow()
        wf.do_login()
        wf.do_add_to_cart()
        wf.do_checkout()
        assert wf.state == "checkout"

    def test_payment_transition(self):
        """S3 → S4: do_pay chuyển từ checkout sang processing."""
        wf = OrderWorkflow()
        wf.do_login()
        wf.do_add_to_cart()
        wf.do_checkout()
        wf.do_pay()
        assert wf.state == "processing"

    def test_confirm_transition(self):
        """S4 → S5: do_confirm chuyển từ processing sang confirmed."""
        wf = OrderWorkflow()
        wf.do_login()
        wf.do_add_to_cart()
        wf.do_checkout()
        wf.do_pay()
        wf.do_confirm()
        assert wf.state == "confirmed"
        assert wf.is_valid_terminal()

    def test_payment_retry(self):
        """S4 → S3 → S4: do_pay_fail cho phép retry từ processing về checkout."""
        wf = OrderWorkflow()
        wf.do_login()
        wf.do_add_to_cart()
        wf.do_checkout()
        wf.do_pay()
        assert wf.state == "processing"
        wf.do_pay_fail()
        assert wf.state == "checkout"
        wf.do_pay()
        wf.do_confirm()
        assert wf.state == "confirmed"

    def test_state_history_recorded(self):
        """FSM ghi lịch sử đầy đủ các trạng thái đã qua."""
        wf = OrderWorkflow()
        wf.do_login()
        wf.do_add_to_cart()
        wf.do_checkout()
        wf.do_pay()
        wf.do_confirm()
        expected_history = ["guest", "authenticated", "cart_active", "checkout", "processing", "confirmed"]
        assert wf.history == expected_history, (
            f"History mismatch:\n  Expected: {expected_history}\n  Actual: {wf.history}"
        )

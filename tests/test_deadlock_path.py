"""
tests/test_deadlock_path.py
============================
Nhóm 2: Deadlock Path Tests
Kiểm thử các kịch bản cố ý tạo deadlock để xác nhận hệ thống PHÁT HIỆN được.
Kỳ vọng: DEADLOCK_DETECTED — hệ thống nhận ra và report đúng.
Kiểm chứng vi phạm AG(¬S6) và sinh Counterexample Report.
"""

import pytest
from utils.fsm_engine import OrderWorkflow
from utils.data_loader import DataLoader
from utils.deadlock_detector import DeadlockDetector


loader = DataLoader()
DEADLOCK_CASES = loader.load_sheet("deadlock")


@pytest.mark.deadlock_path
@pytest.mark.fsm_only
class TestDeadlockPath:
    """
    Nhóm 2: Deadlock Detection Tests
    Xác nhận rằng AG(¬S6) bị vi phạm khi có deadlock,
    và hệ thống phát hiện + báo cáo đúng.
    """

    @pytest.mark.parametrize("tc", DEADLOCK_CASES, ids=[tc["TC_ID"] for tc in DEADLOCK_CASES])
    def test_deadlock_is_detected(self, tc, report):
        """
        DDT: Mỗi TC trong Deadlock_Path PHẢI kết thúc ở trạng thái 'deadlock'.
        Kiểm chứng: hệ thống phát hiện deadlock state và sinh counterexample.
        """
        wf = OrderWorkflow(session_id=tc["TC_ID"])
        events = loader.parse_events(tc["Event_Sequence"])
        wf.apply_events(events)

        actual_state  = wf.state
        is_deadlocked = wf.is_deadlocked()

        # Kỳ vọng: PHẢI đạt deadlock state
        assert actual_state == tc["Expected_State"], (
            f"[{tc['TC_ID']}] Expected deadlock state, got '{actual_state}'.\n"
            f"  Events: {tc['Event_Sequence']}\n"
            f"  Path  : {wf.get_path()}"
        )

        assert is_deadlocked, (
            f"[{tc['TC_ID']}] is_deadlocked() phải trả về True!\n"
            f"  State : {actual_state}\n"
            f"  Path  : {wf.get_path()}"
        )

        # Sinh counterexample
        detector = DeadlockDetector()
        ce = detector.generate_counterexample(
            tc_id=tc["TC_ID"],
            init_state=tc["Init_State"],
            path_taken=wf.history,
            deadlock_state=actual_state,
            reason=tc.get("Notes", "Deadlock state reached"),
        )

        assert ce["verdict"] == "VIOLATED", "Counterexample verdict phải là VIOLATED"
        assert ce["counterexample"] is True

        # Ghi vào report với counterexample
        report.record(
            tc_id=tc["TC_ID"],
            group="Deadlock Path",
            description=tc["Description"],
            event_sequence=tc["Event_Sequence"],
            expected_state=tc["Expected_State"],
            actual_state=actual_state,
            expected_result=tc["Expected_Result"],
            actual_result="DEADLOCK_DETECTED",
            path_taken=wf.get_path(),
            is_deadlock_expected=True,
            counterexample=ce,
        )

    @pytest.mark.parametrize("tc", DEADLOCK_CASES, ids=[tc["TC_ID"] for tc in DEADLOCK_CASES])
    def test_deadlock_not_terminal_valid(self, tc):
        """Deadlock state KHÔNG phải là terminal hợp lệ."""
        wf = OrderWorkflow(session_id=f"{tc['TC_ID']}_terminal_check")
        events = loader.parse_events(tc["Event_Sequence"])
        wf.apply_events(events)

        assert not wf.is_valid_terminal(), (
            f"[{tc['TC_ID']}] Deadlock không được là valid terminal!\n"
            f"  State: {wf.state}"
        )
        assert wf.is_terminal(), (
            f"[{tc['TC_ID']}] Deadlock phải là terminal (không có transition tiếp theo).\n"
            f"  State: {wf.state}"
        )

    def test_ag_property_violated_when_deadlock(self):
        """
        AG(¬S6) bị vi phạm khi FSM đạt trạng thái deadlock.
        FSM graph đơn giản: guest→checkout→deadlock.
        """
        detector = DeadlockDetector()
        fsm_graph = {
            "guest":         ["authenticated"],
            "authenticated": ["cart_active"],
            "cart_active":   ["checkout"],
            "checkout":      ["processing", "deadlock"],   # deadlock reachable!
            "processing":    ["confirmed", "deadlock"],
            "confirmed":     [],
            "deadlock":      [],
            "expired":       ["guest"],
        }
        reachable, paths = detector.check_state_reachability(fsm_graph, "deadlock")
        assert reachable, "Deadlock state phải reachable từ guest trong graph này!"
        assert len(paths) > 0, "Phải có ít nhất 1 path dẫn đến deadlock!"

    def test_direct_deadlock_from_checkout(self):
        """S3 → S6: do_deadlock chuyển trực tiếp từ checkout sang deadlock."""
        wf = OrderWorkflow()
        wf.do_login()
        wf.do_add_to_cart()
        wf.do_checkout()
        wf.do_deadlock()
        assert wf.state == "deadlock"
        assert wf.is_deadlocked()

    def test_direct_deadlock_from_processing(self):
        """S4 → S6: do_deadlock chuyển trực tiếp từ processing sang deadlock."""
        wf = OrderWorkflow()
        wf.do_login()
        wf.do_add_to_cart()
        wf.do_checkout()
        wf.do_pay()
        wf.do_deadlock()
        assert wf.state == "deadlock"
        assert wf.is_deadlocked()

    def test_counterexample_structure(self):
        """Counterexample report phải có đầy đủ các trường bắt buộc."""
        detector = DeadlockDetector()
        ce = detector.generate_counterexample(
            tc_id="TEST_CE",
            init_state="guest",
            path_taken=["guest", "authenticated", "cart_active", "checkout", "deadlock"],
            deadlock_state="deadlock",
            reason="Test circular wait",
        )
        required_keys = ["tc_id", "property", "verdict", "init_state", "path_taken",
                         "deadlock_at", "reason", "counterexample"]
        for key in required_keys:
            assert key in ce, f"Counterexample thiếu trường '{key}'"
        assert ce["property"] == "AG(¬deadlock)"
        assert ce["verdict"] == "VIOLATED"

    def test_deadlock_state_has_no_outgoing_transitions(self):
        """
        Khi đã ở deadlock (S6), không có event nào tiếp tục được.
        Đây là định nghĩa của terminal state bất hợp lệ.
        """
        from transitions import MachineError
        wf = OrderWorkflow()
        wf.do_login()
        wf.do_add_to_cart()
        wf.do_checkout()
        wf.do_deadlock()
        assert wf.state == "deadlock"

        # Thử kích hoạt các event — phải raise MachineError
        for event in ["do_login", "do_checkout", "do_pay", "do_confirm"]:
            with pytest.raises((MachineError, AttributeError)):
                fn = getattr(wf, event)
                fn()

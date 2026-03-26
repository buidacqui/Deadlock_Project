"""
tests/test_concurrent.py
========================
Nhóm 4: Concurrent Tests
Kiểm thử các kịch bản đồng thời (2+ session song song).
Sử dụng ConcurrentWorkflowSimulator + DeadlockDetector (DFS cycle detection).
Phát hiện circular wait trong wait-for graph.
"""

import pytest
from utils.fsm_engine import OrderWorkflow, ConcurrentWorkflowSimulator
from utils.deadlock_detector import DeadlockDetector
from utils.data_loader import DataLoader


loader = DataLoader()
CONCURRENT_CASES = loader.load_sheet("concurrent")


@pytest.mark.concurrent
@pytest.mark.fsm_only
class TestConcurrent:
    """
    Nhóm 4: Concurrent / Multi-Session Tests
    Kiểm tra circular wait trong wait-for graph khi nhiều session song song.
    """

    @pytest.mark.parametrize("tc", CONCURRENT_CASES, ids=[tc["TC_ID"] for tc in CONCURRENT_CASES])
    def test_concurrent_scenario(self, tc, report):
        """
        DDT: Parse CONCURRENT event sequence và chạy multi-session simulation.
        Format: CONCURRENT:session_a=...,session_b=...,conflict=...
        """
        event_str = tc["Event_Sequence"]
        is_deadlock_expected = bool(tc["Is_Deadlock"])

        if event_str.startswith("CONCURRENT:"):
            params = _parse_concurrent_params(event_str)
            result = _run_concurrent_simulation(params)
        else:
            # Fallback: single-session
            wf = OrderWorkflow(session_id=tc["TC_ID"])
            events = loader.parse_events(event_str)
            wf.apply_events(events)
            result = {
                "deadlock": wf.is_deadlocked(),
                "final_state": wf.state,
                "path": wf.get_path(),
                "reason": "Single session run",
            }

        actual_deadlock = result.get("deadlock", False)

        if is_deadlock_expected:
            assert actual_deadlock, (
                f"[{tc['TC_ID']}] Kỳ vọng deadlock nhưng KHÔNG phát hiện!\n"
                f"  Reason: {result.get('reason')}"
            )
            actual_result = "DEADLOCK_DETECTED"
            actual_state  = "deadlock"
        else:
            assert not actual_deadlock, (
                f"[{tc['TC_ID']}] Không kỳ vọng deadlock nhưng phát hiện!\n"
                f"  Reason: {result.get('reason')}"
            )
            actual_result = "PASS"
            actual_state  = tc["Expected_State"]

        report.record(
            tc_id=tc["TC_ID"],
            group="Concurrent",
            description=tc["Description"],
            event_sequence=tc["Event_Sequence"][:80] + "..." if len(tc["Event_Sequence"]) > 80 else tc["Event_Sequence"],
            expected_state=tc["Expected_State"],
            actual_state=actual_state,
            expected_result=tc["Expected_Result"],
            actual_result=actual_result,
            path_taken=result.get("path", "N/A"),
            is_deadlock_expected=is_deadlock_expected,
        )

    # ─── Unit tests cho ConcurrentWorkflowSimulator ─────────

    def test_two_sessions_same_order_deadlock(self, concurrent_sim):
        """
        CC_001: 2 session cùng checkout 1 order → circular wait → deadlock.
        Session A chờ B, B chờ A → DFS phát hiện chu trình.
        """
        sim = concurrent_sim
        sim.add_session("session_a")
        sim.add_session("session_b")

        result = sim.simulate_concurrent_checkout(
            session_a="session_a",
            session_b="session_b",
            shared_order_id="ORDER_001",
        )

        assert result["deadlock"] is True, (
            f"CC_001: Phải phát hiện deadlock!\n  Result: {result}"
        )
        assert "session_a" in result["cycle"] or "session_b" in result["cycle"], (
            f"Cycle phải chứa session IDs: {result['cycle']}"
        )
        assert result["session_a_state"] == "deadlock"
        assert result["session_b_state"] == "deadlock"

    def test_two_sessions_different_orders_no_deadlock(self, concurrent_sim):
        """
        CC_004: 2 session checkout 2 order khác nhau → không có circular wait.
        """
        sim = concurrent_sim
        wf_a = sim.add_session("session_a")
        wf_b = sim.add_session("session_b")

        # Hai session hoàn toàn độc lập
        wf_a.apply_events(["do_login", "do_add_to_cart", "do_checkout", "do_pay", "do_confirm"])
        wf_b.apply_events(["do_login", "do_add_to_cart", "do_checkout", "do_pay", "do_confirm"])

        # Không có waiting relationship
        has_cycle, cycle = sim.has_circular_wait()

        assert not has_cycle, (
            f"CC_004: Không được phép có deadlock với 2 order độc lập!\n  Cycle: {cycle}"
        )
        assert wf_a.state == "confirmed"
        assert wf_b.state == "confirmed"

    def test_three_session_circular_wait(self):
        """
        CC_003: 3-session circular wait A→B→C→A.
        DFS phát hiện chu trình độ dài 3.
        """
        detector = DeadlockDetector()
        wait_for_graph = {
            "session_a": ["session_b"],   # A chờ B
            "session_b": ["session_c"],   # B chờ C
            "session_c": ["session_a"],   # C chờ A → CIRCULAR!
        }

        has_cycle, cycle = detector.detect_cycle(wait_for_graph)

        assert has_cycle, "DFS phải phát hiện chu trình 3 session!"
        assert len(cycle) >= 3, f"Cycle phải có ít nhất 3 node: {cycle}"

    def test_no_cycle_in_linear_wait(self):
        """
        Wait graph tuyến tính (A→B→C) không có chu trình → không deadlock.
        """
        detector = DeadlockDetector()
        wait_for_graph = {
            "session_a": ["session_b"],
            "session_b": ["session_c"],
            "session_c": [],              # C không chờ ai
        }

        has_cycle, cycle = detector.detect_cycle(wait_for_graph)

        assert not has_cycle, f"Graph tuyến tính không có deadlock! Cycle: {cycle}"
        assert cycle == []

    def test_self_loop_is_deadlock(self):
        """Session A chờ chính mình → self-loop → deadlock."""
        detector = DeadlockDetector()
        wait_for_graph = {
            "session_a": ["session_a"],   # self-loop
        }
        has_cycle, cycle = detector.detect_cycle(wait_for_graph)
        assert has_cycle, "Self-loop phải là deadlock!"

    def test_empty_wait_graph_no_deadlock(self):
        """Wait-for graph rỗng → không có deadlock."""
        detector = DeadlockDetector()
        has_cycle, cycle = detector.detect_cycle({})
        assert not has_cycle
        assert cycle == []

    def test_session_b_timeout_avoids_deadlock(self, concurrent_sim):
        """
        CC_002: Session B timeout (session expire) trước khi circular wait xảy ra
        → thoát ra khỏi vòng chờ → không deadlock.
        """
        sim = concurrent_sim
        wf_a = sim.add_session("session_a")
        wf_b = sim.add_session("session_b")

        # A tiến đến checkout và giữ lock
        wf_a.apply_events(["do_login", "do_add_to_cart", "do_checkout"])

        # B timeout trước khi tạo circular wait
        wf_b.apply_events(["do_login", "do_add_to_cart", "do_session_expire", "do_restore"])

        # A không bị block → không có circular wait
        has_cycle, cycle = sim.has_circular_wait()
        assert not has_cycle, (
            f"CC_002: B timeout → không được deadlock!\n  Cycle: {cycle}"
        )
        assert wf_b.state == "guest", f"B phải về guest sau restore, got '{wf_b.state}'"
        assert not wf_a.is_deadlocked()
        assert not wf_b.is_deadlocked()

    def test_isolated_deadlock_does_not_affect_other_session(self, concurrent_sim):
        """
        CC_006: Session A deadlock, Session B hoàn thành bình thường.
        Deadlock isolated — không lây sang session khác.
        """
        sim = concurrent_sim
        wf_a = sim.add_session("session_a")
        wf_b = sim.add_session("session_b")

        # A bị deadlock
        wf_a.apply_events(["do_login", "do_add_to_cart", "do_checkout", "do_deadlock"])

        # B độc lập, hoàn thành bình thường
        wf_b.apply_events(["do_login", "do_add_to_cart", "do_checkout", "do_pay", "do_confirm"])

        assert wf_a.is_deadlocked(), "A phải ở trạng thái deadlock"
        assert wf_b.state == "confirmed", f"B phải ở confirmed, got '{wf_b.state}'"
        assert not wf_b.is_deadlocked(), "B KHÔNG được bị ảnh hưởng bởi deadlock của A"

    def test_dfs_detects_two_node_cycle(self):
        """Chu trình đơn giản nhất: A→B→A."""
        detector = DeadlockDetector()
        wait_for_graph = {
            "A": ["B"],
            "B": ["A"],
        }
        has_cycle, cycle = detector.detect_cycle(wait_for_graph)
        assert has_cycle
        assert "A" in cycle and "B" in cycle

    def test_concurrent_sim_multiple_sessions(self, concurrent_sim):
        """Simulator quản lý nhiều session độc lập."""
        sim = concurrent_sim
        for i in range(5):
            sim.add_session(f"session_{i}")
        assert len(sim.sessions) == 5


# ─── Helpers ─────────────────────────────────────────────────

def _parse_concurrent_params(event_str: str) -> dict:
    """
    Parse CONCURRENT event string thành dict tham số.
    Format: CONCURRENT:session_a=ev1+ev2,session_b=ev1+ev2,conflict=type
    """
    params = {}
    content = event_str.replace("CONCURRENT:", "")
    for part in content.split(","):
        if "=" in part:
            key, val = part.split("=", 1)
            params[key.strip()] = val.strip()
    return params


def _run_concurrent_simulation(params: dict) -> dict:
    """Chạy concurrent simulation dựa trên params đã parse."""
    sim = ConcurrentWorkflowSimulator()
    conflict = params.get("conflict", "no_conflict")

    sessions = {}
    for key, val in params.items():
        if key.startswith("session_") and key != "conflict":
            wf = sim.add_session(key)
            events = [e.strip() for e in val.split("+") if e.strip()]
            wf.apply_events(events)
            sessions[key] = wf

    if conflict in ("same_order", "circular_3", "payment_gateway"):
        # Thiết lập wait relationships để mô phỏng tranh chấp
        session_ids = list(sessions.keys())
        if len(session_ids) >= 2:
            if conflict == "circular_3" and len(session_ids) >= 3:
                sim.set_waiting(session_ids[0], session_ids[1])
                sim.set_waiting(session_ids[1], session_ids[2])
                sim.set_waiting(session_ids[2], session_ids[0])
            else:
                sim.set_waiting(session_ids[0], session_ids[1])
                sim.set_waiting(session_ids[1], session_ids[0])

    has_cycle, cycle = sim.has_circular_wait()

    if has_cycle:
        for wf in sessions.values():
            if wf.state == "checkout" or wf.state == "processing":
                wf.do_deadlock()
                wf.set_deadlock_reason(f"Circular wait: {' → '.join(cycle)}")

    first_session = next(iter(sessions.values())) if sessions else None

    return {
        "deadlock": has_cycle,
        "cycle": cycle,
        "path": first_session.get_path() if first_session else "N/A",
        "reason": f"Circular wait: {cycle}" if has_cycle else "No circular wait",
    }

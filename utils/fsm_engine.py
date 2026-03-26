"""
utils/fsm_engine.py
===================
Finite State Machine engine — thuần Python, không dependency ngoài.
8 trạng thái (S0-S7), 20+ transitions, tích hợp DeadlockDetector.
"""
import logging
from utils.deadlock_detector import DeadlockDetector

logger = logging.getLogger(__name__)

TRANSITION_TABLE: dict[tuple[str,str], str] = {
    ("guest",         "do_login"):           "authenticated",
    ("guest",         "do_login_fail"):      "guest",
    ("authenticated", "do_login"):           "authenticated",  # re-login
    ("authenticated", "do_add_to_cart"):     "cart_active",
    ("authenticated", "do_session_expire"):  "expired",
    ("cart_active",   "do_add_to_cart"):     "cart_active",
    ("cart_active",   "do_empty_cart"):      "cart_active",
    ("cart_active",   "do_checkout"):        "checkout",
    ("cart_active",   "do_cancel"):          "authenticated",
    ("authenticated", "do_cancel"):         "guest",          # hủy, về guest
    ("cart_active",   "do_session_expire"):  "expired",
    ("checkout",      "do_pay"):             "processing",
    ("checkout",      "do_cancel"):          "cart_active",
    ("checkout",      "do_session_expire"):  "expired",
    ("checkout",      "do_deadlock"):        "deadlock",
    ("processing",    "do_confirm"):         "confirmed",
    ("processing",    "do_pay_fail"):        "checkout",
    ("processing",    "do_session_expire"):  "expired",
    ("processing",    "do_deadlock"):        "deadlock",
    ("expired",       "do_restore"):         "guest",
}

TERMINAL_STATES   = {"confirmed", "deadlock"}
VALID_TERMINALS   = {"confirmed"}


class OrderWorkflow:
    def __init__(self, session_id: str = "default"):
        self.session_id    = session_id
        self.state         = "guest"
        self.history: list[str] = ["guest"]
        self._deadlock_reason: str = ""

    def _trigger(self, event: str):
        key = (self.state, event)
        next_state = TRANSITION_TABLE.get(key)
        if next_state is None:
            raise ValueError(f"[{self.session_id}] Invalid: ({self.state}, {event})")
        logger.debug(f"[{self.session_id}] {self.state} --{event}--> {next_state}")
        self.state = next_state
        self.history.append(next_state)

    # --- trigger shortcuts ---
    def do_login(self):           self._trigger("do_login")
    def do_login_fail(self):      self._trigger("do_login_fail")
    def do_add_to_cart(self):     self._trigger("do_add_to_cart")
    def do_empty_cart(self):      self._trigger("do_empty_cart")
    def do_checkout(self):        self._trigger("do_checkout")
    def do_cancel(self):          self._trigger("do_cancel")
    def do_pay(self):             self._trigger("do_pay")
    def do_pay_fail(self):        self._trigger("do_pay_fail")
    def do_confirm(self):         self._trigger("do_confirm")
    def do_session_expire(self):  self._trigger("do_session_expire")
    def do_restore(self):         self._trigger("do_restore")
    def do_deadlock(self):        self._trigger("do_deadlock")

    # --- helpers ---
    def is_deadlocked(self) -> bool:     return self.state == "deadlock"
    def is_terminal(self) -> bool:       return self.state in TERMINAL_STATES
    def is_valid_terminal(self) -> bool: return self.state in VALID_TERMINALS
    def get_path(self) -> str:           return " → ".join(self.history)
    def set_deadlock_reason(self, r):    self._deadlock_reason = r
    def get_deadlock_reason(self) -> str: return self._deadlock_reason

    def apply_events(self, events: list[str]) -> bool:
        for ev in events:
            ev = ev.strip()
            if not ev: continue
            try:
                self._trigger(ev)
            except ValueError as e:
                logger.error(str(e))
                return False
        return True

    def reset(self):
        self.state = "guest"
        self.history = ["guest"]
        self._deadlock_reason = ""


class ConcurrentWorkflowSimulator:
    def __init__(self):
        self.sessions: dict[str, OrderWorkflow] = {}
        self.wait_for_graph: dict[str, list[str]] = {}
        self.detector = DeadlockDetector()

    def add_session(self, sid: str) -> OrderWorkflow:
        wf = OrderWorkflow(session_id=sid)
        self.sessions[sid] = wf
        self.wait_for_graph[sid] = []
        return wf

    def set_waiting(self, sid: str, waiting_for: str):
        if sid in self.wait_for_graph:
            if waiting_for not in self.wait_for_graph[sid]:
                self.wait_for_graph[sid].append(waiting_for)

    def has_circular_wait(self) -> tuple[bool, list[str]]:
        return self.detector.detect_cycle(self.wait_for_graph)

    def simulate_concurrent_checkout(self, session_a, session_b, shared_order_id) -> dict:
        wf_a = self.sessions.get(session_a)
        wf_b = self.sessions.get(session_b)
        if not wf_a or not wf_b:
            return {"deadlock": False, "reason": "Session not found"}
        wf_a.apply_events(["do_login","do_add_to_cart","do_checkout"])
        wf_b.apply_events(["do_login","do_add_to_cart","do_checkout"])
        self.set_waiting(session_a, session_b)
        self.set_waiting(session_b, session_a)
        has_cycle, cycle = self.has_circular_wait()
        reason = ""
        if has_cycle:
            reason = f"Circular wait: {' → '.join(cycle)}"
            wf_a.do_deadlock(); wf_a.set_deadlock_reason(reason)
            wf_b.do_deadlock(); wf_b.set_deadlock_reason(reason)
        return {
            "deadlock": has_cycle, "cycle": cycle,
            "shared_order": shared_order_id,
            "session_a_state": wf_a.state,
            "session_b_state": wf_b.state,
            "reason": reason if has_cycle else "No circular wait",
        }

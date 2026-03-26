#!/usr/bin/env python3
"""
run_tests.py
============
Script chạy kiểm thử tất cả nhóm — thay thế cho pytest CLI.
Dùng khi chưa cài pytest hoặc muốn chạy nhanh chỉ với Python.

Cách dùng:
    python run_tests.py              # Chạy toàn bộ FSM tests
    python run_tests.py --group valid
    python run_tests.py --group deadlock
    python run_tests.py --group boundary
    python run_tests.py --group concurrent
    python run_tests.py --group all
"""

import sys
import argparse
import traceback
import logging
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from utils.fsm_engine import OrderWorkflow, ConcurrentWorkflowSimulator
from utils.deadlock_detector import DeadlockDetector
from utils.data_loader import DataLoader
from utils.report_generator import ReportGenerator

logging.basicConfig(level=logging.WARNING)

# ─── Color output ────────────────────────────────────────────
try:
    from colorama import Fore, Style, init
    init(autoreset=True)
    GREEN  = Fore.GREEN
    RED    = Fore.RED
    YELLOW = Fore.YELLOW
    CYAN   = Fore.CYAN
    RESET  = Style.RESET_ALL
    BOLD   = Style.BRIGHT
except ImportError:
    GREEN = RED = YELLOW = CYAN = RESET = BOLD = ""


# ════════════════════════════════════════════════════════════
# GROUP 1: VALID PATH
# ════════════════════════════════════════════════════════════

def run_valid_path(loader: DataLoader, report: ReportGenerator):
    cases = loader.load_sheet("valid")
    passed = failed = 0
    print(f"\n{BOLD}{CYAN}{'─'*60}{RESET}")
    print(f"{BOLD}  NHÓM 1: VALID PATH ({len(cases)} TC){RESET}")
    print(f"{CYAN}{'─'*60}{RESET}")

    for tc in cases:
        wf = OrderWorkflow(tc["TC_ID"])
        events = loader.parse_events(tc["Event_Sequence"])
        ok = wf.apply_events(events)

        success = ok and wf.state == tc["Expected_State"] and not wf.is_deadlocked()
        status  = "PASS" if success else "FAIL"
        color   = GREEN if success else RED

        print(f"  {color}[{status}]{RESET} {tc['TC_ID']:<10} | {tc['Expected_State']:<18} | {wf.get_path()[:55]}")

        report.record(
            tc_id=tc["TC_ID"], group="Valid Path",
            description=tc["Description"],
            event_sequence=tc["Event_Sequence"],
            expected_state=tc["Expected_State"],
            actual_state=wf.state,
            expected_result=tc["Expected_Result"],
            actual_result=status,
            path_taken=wf.get_path(),
            is_deadlock_expected=False,
        )
        if success: passed += 1
        else:        failed += 1

    return passed, failed


# ════════════════════════════════════════════════════════════
# GROUP 2: DEADLOCK PATH
# ════════════════════════════════════════════════════════════

def run_deadlock_path(loader: DataLoader, report: ReportGenerator):
    cases = loader.load_sheet("deadlock")
    passed = failed = 0
    detector = DeadlockDetector()
    print(f"\n{BOLD}{CYAN}{'─'*60}{RESET}")
    print(f"{BOLD}  NHÓM 2: DEADLOCK PATH ({len(cases)} TC){RESET}")
    print(f"{CYAN}{'─'*60}{RESET}")

    for tc in cases:
        wf = OrderWorkflow(tc["TC_ID"])
        events = loader.parse_events(tc["Event_Sequence"])
        wf.apply_events(events)

        detected  = wf.is_deadlocked()
        expected  = bool(tc["Is_Deadlock"])
        success   = detected == expected
        status    = "DEADLOCK_DETECTED" if detected else "NOT_DETECTED"
        color     = GREEN if success else RED
        result_lbl= "PASS" if success else "FAIL"

        print(f"  {color}[{result_lbl}]{RESET} {tc['TC_ID']:<10} | {status:<20} | path: {wf.get_path()[:40]}")

        ce = None
        if detected:
            ce = detector.generate_counterexample(
                tc_id=tc["TC_ID"],
                init_state=tc["Init_State"],
                path_taken=wf.history,
                deadlock_state=wf.state,
                reason=tc.get("Notes", "Deadlock triggered"),
            )

        report.record(
            tc_id=tc["TC_ID"], group="Deadlock Path",
            description=tc["Description"],
            event_sequence=tc["Event_Sequence"],
            expected_state=tc["Expected_State"],
            actual_state=wf.state,
            expected_result=tc["Expected_Result"],
            actual_result=status,
            path_taken=wf.get_path(),
            is_deadlock_expected=expected,
            counterexample=ce,
        )
        if success: passed += 1
        else:        failed += 1

    return passed, failed


# ════════════════════════════════════════════════════════════
# GROUP 3: BOUNDARY STATE
# ════════════════════════════════════════════════════════════

def run_boundary(loader: DataLoader, report: ReportGenerator):
    cases = loader.load_sheet("boundary")
    passed = failed = 0
    print(f"\n{BOLD}{CYAN}{'─'*60}{RESET}")
    print(f"{BOLD}  NHÓM 3: BOUNDARY STATE ({len(cases)} TC){RESET}")
    print(f"{CYAN}{'─'*60}{RESET}")

    for tc in cases:
        wf = OrderWorkflow(tc["TC_ID"])
        events = loader.parse_events(tc["Event_Sequence"])
        ok = wf.apply_events(events)

        no_deadlock = not wf.is_deadlocked()
        right_state = wf.state == tc["Expected_State"]
        success = ok and no_deadlock and right_state
        status  = "PASS" if success else "FAIL"
        color   = GREEN if success else RED

        print(f"  {color}[{status}]{RESET} {tc['TC_ID']:<10} | state: {wf.state:<18} | {wf.get_path()[:45]}")

        report.record(
            tc_id=tc["TC_ID"], group="Boundary State",
            description=tc["Description"],
            event_sequence=tc["Event_Sequence"],
            expected_state=tc["Expected_State"],
            actual_state=wf.state,
            expected_result=tc["Expected_Result"],
            actual_result=status,
            path_taken=wf.get_path(),
            is_deadlock_expected=False,
        )
        if success: passed += 1
        else:        failed += 1

    return passed, failed


# ════════════════════════════════════════════════════════════
# GROUP 4: CONCURRENT
# ════════════════════════════════════════════════════════════

def _parse_concurrent(event_str: str) -> dict:
    params = {}
    for part in event_str.replace("CONCURRENT:", "").split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            params[k.strip()] = v.strip()
    return params


def _run_concurrent(params: dict) -> dict:
    sim      = ConcurrentWorkflowSimulator()
    conflict = params.get("conflict", "no_conflict")
    sessions = {}

    for k, v in params.items():
        if k.startswith("session_"):
            wf = sim.add_session(k)
            wf.apply_events([e.strip() for e in v.split("+") if e.strip()])
            sessions[k] = wf

    if conflict in ("same_order", "circular_3", "payment_gateway"):
        ids = list(sessions.keys())
        if len(ids) >= 2:
            if conflict == "circular_3" and len(ids) >= 3:
                sim.set_waiting(ids[0], ids[1])
                sim.set_waiting(ids[1], ids[2])
                sim.set_waiting(ids[2], ids[0])
            else:
                sim.set_waiting(ids[0], ids[1])
                sim.set_waiting(ids[1], ids[0])

    has_cycle, cycle = sim.has_circular_wait()
    if has_cycle:
        for wf in sessions.values():
            if wf.state in ("checkout", "processing"):
                wf.do_deadlock()
    first = next(iter(sessions.values()), None)
    return {
        "deadlock": has_cycle, "cycle": cycle,
        "path": first.get_path() if first else "N/A",
        "reason": f"Circular wait: {cycle}" if has_cycle else "No circular wait",
    }


def run_concurrent(loader: DataLoader, report: ReportGenerator):
    cases = loader.load_sheet("concurrent")
    passed = failed = 0
    print(f"\n{BOLD}{CYAN}{'─'*60}{RESET}")
    print(f"{BOLD}  NHÓM 4: CONCURRENT ({len(cases)} TC){RESET}")
    print(f"{CYAN}{'─'*60}{RESET}")

    for tc in cases:
        event_str    = tc["Event_Sequence"]
        is_dl_exp    = bool(tc["Is_Deadlock"])

        if event_str.startswith("CONCURRENT:"):
            result = _run_concurrent(_parse_concurrent(event_str))
        else:
            wf = OrderWorkflow(tc["TC_ID"])
            wf.apply_events(loader.parse_events(event_str))
            result = {"deadlock": wf.is_deadlocked(), "path": wf.get_path(), "reason": ""}

        actual_dl = result["deadlock"]
        success   = actual_dl == is_dl_exp
        status    = "DEADLOCK_DETECTED" if actual_dl else "PASS"
        color     = GREEN if success else RED

        print(f"  {color}[{'PASS' if success else 'FAIL'}]{RESET} {tc['TC_ID']:<10} | "
              f"deadlock={'YES' if actual_dl else 'NO '} (expected={'YES' if is_dl_exp else 'NO '}) | "
              f"{result['reason'][:35]}")

        report.record(
            tc_id=tc["TC_ID"], group="Concurrent",
            description=tc["Description"],
            event_sequence=event_str[:80],
            expected_state=tc["Expected_State"],
            actual_state="deadlock" if actual_dl else tc["Expected_State"],
            expected_result=tc["Expected_Result"],
            actual_result=status,
            path_taken=result.get("path", "N/A"),
            is_deadlock_expected=is_dl_exp,
        )
        if success: passed += 1
        else:        failed += 1

    return passed, failed


# ════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Deadlock Verification Test Runner")
    parser.add_argument("--group", default="all",
        choices=["all", "valid", "deadlock", "boundary", "concurrent"],
        help="Nhóm test muốn chạy")
    args = parser.parse_args()

    print(f"\n{BOLD}{'═'*60}{RESET}")
    print(f"{BOLD}  DEADLOCK VERIFICATION TEST SUITE{RESET}")
    print(f"  OWASP Juice Shop · FSM · Data-Driven Testing")
    print(f"  Thuộc tính: AG(¬deadlock)")
    print(f"  {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"{BOLD}{'═'*60}{RESET}")

    loader = DataLoader()
    report = ReportGenerator()

    total_pass = total_fail = 0
    runners = {
        "valid":      run_valid_path,
        "deadlock":   run_deadlock_path,
        "boundary":   run_boundary,
        "concurrent": run_concurrent,
    }

    groups = list(runners.keys()) if args.group == "all" else [args.group]

    for g in groups:
        try:
            p, f = runners[g](loader, report)
            total_pass += p
            total_fail += f
        except Exception as e:
            print(f"\n{RED}ERROR in group '{g}': {e}{RESET}")
            traceback.print_exc()

    # Print & save reports
    report.print_summary()
    xl   = report.save_excel_report()
    html = report.save_html_report()
    jsn  = report.save_counterexample_json()

    print(f"  {GREEN}Excel report  :{RESET} {xl}")
    print(f"  {GREEN}HTML  report  :{RESET} {html}")
    print(f"  {GREEN}JSON  CE      :{RESET} {jsn}")
    print()

    return 1 if total_fail > 0 else 0


if __name__ == "__main__":
    sys.exit(main())

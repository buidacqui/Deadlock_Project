"""
utils/report_generator.py
==========================
Tự động sinh Counterexample Report và HTML Test Report.
Ghi nhận kết quả thực tế vào file Excel sau mỗi lần chạy.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
import pandas as pd
from tabulate import tabulate
from colorama import Fore, Style, init

init(autoreset=True)
logger = logging.getLogger(__name__)

REPORTS_DIR = Path(__file__).parent.parent / "reports"


class ReportGenerator:
    """
    Tổng hợp kết quả kiểm thử và xuất báo cáo.
    """

    def __init__(self):
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        self.results: list[dict] = []
        self.counterexamples: list[dict] = []
        self.run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    def record(
        self,
        tc_id: str,
        group: str,
        description: str,
        event_sequence: str,
        expected_state: str,
        actual_state: str,
        expected_result: str,
        actual_result: str,
        path_taken: str,
        is_deadlock_expected: bool,
        counterexample: Optional[dict] = None,
    ):
        passed = expected_result.upper() == actual_result.upper()

        entry = {
            "TC_ID":             tc_id,
            "Group":             group,
            "Description":       description,
            "Event_Sequence":    event_sequence,
            "Expected_State":    expected_state,
            "Actual_State":      actual_state,
            "Expected_Result":   expected_result,
            "Actual_Result":     actual_result,
            "Path_Taken":        path_taken,
            "Is_Deadlock_Expected": is_deadlock_expected,
            "Status":            "PASS" if passed else "FAIL",
            "Timestamp":         datetime.now().isoformat(),
        }

        self.results.append(entry)

        if counterexample:
            self.counterexamples.append({**entry, **counterexample})

        # Console output
        status_color = Fore.GREEN if passed else Fore.RED
        print(
            f"  {status_color}[{entry['Status']}]{Style.RESET_ALL} "
            f"{tc_id:<12} | {group:<12} | "
            f"Expected: {expected_state:<18} | Actual: {actual_state}"
        )

    def print_summary(self):
        """In tổng kết ra console."""
        total  = len(self.results)
        passed = sum(1 for r in self.results if r["Status"] == "PASS")
        failed = total - passed

        print("\n" + "=" * 70)
        print(f"  {'TỔNG KẾT KIỂM THỬ':^66}")
        print("=" * 70)
        print(f"  Tổng số TC   : {total}")
        print(f"  {Fore.GREEN}PASS          : {passed}{Style.RESET_ALL}")
        print(f"  {Fore.RED}FAIL          : {failed}{Style.RESET_ALL}")
        print(f"  Tỉ lệ thành công: {passed/total*100:.1f}%")

        if self.counterexamples:
            print(f"\n  {Fore.RED}Counterexamples phát hiện: {len(self.counterexamples)}{Style.RESET_ALL}")
            for ce in self.counterexamples:
                print(f"    ✗ {ce['TC_ID']} — {ce.get('reason', 'Deadlock detected')}")
                print(f"      Path: {ce['Path_Taken']}")

        print("=" * 70 + "\n")

    def save_excel_report(self, filepath: Optional[Path] = None) -> Path:
        """Ghi kết quả vào Excel."""
        if not filepath:
            filepath = REPORTS_DIR / f"test_results_{self.run_timestamp}.xlsx"

        df = pd.DataFrame(self.results)
        with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="All_Results", index=False)

            # Sheet riêng cho counterexamples
            if self.counterexamples:
                ce_df = pd.DataFrame(self.counterexamples)
                ce_df.to_excel(writer, sheet_name="Counterexamples", index=False)

            # Summary sheet
            summary = {
                "Metric": ["Total", "PASS", "FAIL", "Pass Rate", "Counterexamples"],
                "Value": [
                    len(self.results),
                    sum(1 for r in self.results if r["Status"] == "PASS"),
                    sum(1 for r in self.results if r["Status"] == "FAIL"),
                    f"{sum(1 for r in self.results if r['Status']=='PASS')/len(self.results)*100:.1f}%",
                    len(self.counterexamples),
                ]
            }
            pd.DataFrame(summary).to_excel(writer, sheet_name="Summary", index=False)

        logger.info(f"Excel report saved: {filepath}")
        return filepath

    def save_html_report(self, filepath: Optional[Path] = None) -> Path:
        """Sinh HTML report trực quan."""
        if not filepath:
            filepath = REPORTS_DIR / f"test_report_{self.run_timestamp}.html"

        total  = len(self.results)
        passed = sum(1 for r in self.results if r["Status"] == "PASS")
        failed = total - passed
        pass_rate = passed / total * 100 if total else 0

        rows_html = ""
        for r in self.results:
            status_cls = "pass" if r["Status"] == "PASS" else "fail"
            rows_html += f"""
            <tr class="{status_cls}">
              <td>{r['TC_ID']}</td>
              <td>{r['Group']}</td>
              <td>{r['Description']}</td>
              <td><code>{r['Event_Sequence']}</code></td>
              <td>{r['Expected_State']}</td>
              <td>{r['Actual_State']}</td>
              <td><span class="badge {status_cls}">{r['Status']}</span></td>
              <td>{r['Timestamp'][:19]}</td>
            </tr>"""

        ce_html = ""
        for ce in self.counterexamples:
            ce_html += f"""
            <div class="counterexample">
              <div class="ce-header">⚠ COUNTEREXAMPLE — {ce['TC_ID']}</div>
              <table class="ce-table">
                <tr><td>Property</td><td><code>AG(¬deadlock)</code> — <strong>VIOLATED</strong></td></tr>
                <tr><td>Init State</td><td>{ce.get('init_state', ce['Expected_State'])}</td></tr>
                <tr><td>Path Taken</td><td><code>{ce['Path_Taken']}</code></td></tr>
                <tr><td>Deadlock At</td><td class="red">{ce['Actual_State']}</td></tr>
                <tr><td>Reason</td><td>{ce.get('reason', 'Deadlock state reached')}</td></tr>
              </table>
            </div>"""

        html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <title>Test Report — Absence of Deadlock</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f5f5f0; color: #1a1a1a; }}
    .header {{ background: #1e1e2e; color: white; padding: 32px 48px; }}
    .header h1 {{ font-size: 26px; font-weight: 700; letter-spacing: 1px; }}
    .header p {{ color: #aaaacc; margin-top: 6px; font-size: 14px; }}
    .summary {{ display: flex; gap: 16px; padding: 24px 48px; background: #e8e8e3; border-bottom: 1px solid #ccc; }}
    .stat {{ background: white; border-radius: 8px; padding: 16px 24px; text-align: center; min-width: 120px; }}
    .stat .n {{ font-size: 32px; font-weight: 700; }}
    .stat .l {{ font-size: 12px; color: #777; margin-top: 4px; }}
    .stat.green .n {{ color: #3b6d11; }}
    .stat.red .n {{ color: #a32d2d; }}
    .stat.purple .n {{ color: #3c3489; }}
    .content {{ padding: 24px 48px; }}
    h2 {{ font-size: 18px; font-weight: 700; margin: 24px 0 12px; color: #3c3489; }}
    table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
    th {{ background: #3c3489; color: white; padding: 10px 14px; font-size: 12px; text-align: left; }}
    td {{ padding: 9px 14px; font-size: 12px; border-bottom: 1px solid #eee; }}
    tr.pass td {{ background: #f6fbf3; }}
    tr.fail td {{ background: #fdf5f5; }}
    tr:hover td {{ filter: brightness(0.97); }}
    .badge {{ display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 11px; font-weight: 700; }}
    .badge.pass {{ background: #e6f4e0; color: #3b6d11; }}
    .badge.fail {{ background: #fde8e8; color: #a32d2d; }}
    code {{ background: #f0eff0; padding: 2px 6px; border-radius: 4px; font-size: 11px; }}
    .counterexample {{ background: #fff5f5; border: 1.5px solid #e9a9a9; border-radius: 8px; padding: 18px 22px; margin: 12px 0; }}
    .ce-header {{ font-size: 15px; font-weight: 700; color: #a32d2d; margin-bottom: 12px; }}
    .ce-table {{ width: auto; box-shadow: none; }}
    .ce-table td {{ border: none; padding: 4px 16px 4px 0; background: transparent; }}
    .ce-table td:first-child {{ font-weight: 600; color: #555; width: 120px; }}
    .red {{ color: #a32d2d; font-weight: 700; }}
    .footer {{ text-align: center; padding: 24px; color: #aaa; font-size: 12px; }}
  </style>
</head>
<body>
  <div class="header">
    <h1>TEST REPORT — Kiểm chứng Absence of Deadlock</h1>
    <p>OWASP Juice Shop · FSM · Data-Driven Testing · {self.run_timestamp}</p>
  </div>

  <div class="summary">
    <div class="stat purple"><div class="n">{total}</div><div class="l">Tổng TC</div></div>
    <div class="stat green"><div class="n">{passed}</div><div class="l">PASS</div></div>
    <div class="stat red"><div class="n">{failed}</div><div class="l">FAIL</div></div>
    <div class="stat"><div class="n">{pass_rate:.1f}%</div><div class="l">Pass Rate</div></div>
    <div class="stat red"><div class="n">{len(self.counterexamples)}</div><div class="l">Counterexamples</div></div>
  </div>

  <div class="content">
    {"<h2>⚠ Counterexample Report</h2>" + ce_html if self.counterexamples else ""}

    <h2>Kết quả chi tiết ({total} test cases)</h2>
    <table>
      <thead>
        <tr>
          <th>TC_ID</th><th>Nhóm</th><th>Mô tả</th>
          <th>Event Sequence</th><th>Expected State</th>
          <th>Actual State</th><th>Status</th><th>Thời gian</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
  </div>

  <div class="footer">
    Báo cáo được tự động sinh bởi DeadlockTestSuite · {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
  </div>
</body>
</html>"""

        filepath.write_text(html, encoding="utf-8")
        logger.info(f"HTML report saved: {filepath}")
        return filepath

    def save_counterexample_json(self, filepath: Optional[Path] = None) -> Path:
        """Xuất counterexamples dưới dạng JSON để tích hợp CI/CD."""
        if not filepath:
            filepath = REPORTS_DIR / f"counterexamples_{self.run_timestamp}.json"

        data = {
            "run_timestamp": self.run_timestamp,
            "property": "AG(¬deadlock)",
            "total_violations": len(self.counterexamples),
            "counterexamples": self.counterexamples,
        }
        filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info(f"Counterexample JSON saved: {filepath}")
        return filepath

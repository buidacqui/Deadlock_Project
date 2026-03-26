#!/bin/bash
# run_tests.sh — Chạy kiểm thử Absence of Deadlock
# Dùng: ./run_tests.sh [all|group1|group2|group3|group4|ui|allure]
set -e
CYAN="\033[0;36m"; GREEN="\033[0;32m"; YELLOW="\033[1;33m"; RED="\033[0;31m"; NC="\033[0m"
cd "$(dirname "$0")"
echo -e "${CYAN}═══ Absence of Deadlock Test Suite ═══${NC}"

# Venv
[ ! -d "venv" ] && python3 -m venv venv
source venv/bin/activate 2>/dev/null || source venv/Scripts/activate 2>/dev/null

# Dependencies
pip install -r requirements.txt -q
playwright install chromium --with-deps -q 2>/dev/null || true

# Test data
python utils/generate_test_data.py
mkdir -p reports

MODE="${1:-all}"
case "$MODE" in
  group1) pytest -m valid_path    -v --tb=short --html=reports/report_group1.html --self-contained-html ;;
  group2) pytest -m deadlock_path -v --tb=short --html=reports/report_group2.html --self-contained-html ;;
  group3) pytest -m boundary      -v --tb=short --html=reports/report_group3.html --self-contained-html ;;
  group4) pytest -m concurrent    -v --tb=short --html=reports/report_group4.html --self-contained-html ;;
  ui)
    curl -s http://localhost:3000 > /dev/null 2>&1 || { echo -e "${RED}✗ Juice Shop chưa chạy. Chạy: docker compose up -d juice-shop${NC}"; exit 1; }
    pytest -m "fsm_only or ui" -v --tb=short --html=reports/report_full.html --self-contained-html ;;
  allure)
    pytest -m fsm_only --alluredir=reports/allure_results -v
    allure serve reports/allure_results ;;
  *)
    pytest -m fsm_only -v --tb=short --html=reports/report_all.html --self-contained-html ;;
esac

echo -e "${GREEN}✓ Xong! Xem reports/ để xem kết quả.${NC}"

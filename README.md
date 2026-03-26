# Kiểm chứng Absence of Deadlock — OWASP Juice Shop

**Python + pytest + Playwright · FSM · Data-Driven Testing · Docker**

## Cài đặt nhanh

```bash
# 1. Tạo venv & cài packages
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# 2. Sinh Excel test data
python utils/generate_test_data.py

# 3. Chạy Juice Shop
docker compose up -d juice-shop

# 4. Chạy toàn bộ tests
./run_tests.sh          # FSM tests (không cần browser)
./run_tests.sh ui       # FSM + UI tests
```

## Cấu trúc

```
deadlock_project/
├── utils/
│   ├── fsm_engine.py          FSM 8 trạng thái (S0-S7)
│   ├── deadlock_detector.py   DFS Cycle Detection
│   ├── data_loader.py         Đọc Excel DDT
│   ├── report_generator.py    HTML/Excel/JSON report
│   └── generate_test_data.py  Tạo test data Excel
├── tests/
│   ├── test_valid_path.py     Nhóm 1: Valid Path (10 TC)
│   ├── test_deadlock_path.py  Nhóm 2: Deadlock Detection (8 TC)
│   ├── test_boundary_state.py Nhóm 3: Boundary State (8 TC)
│   ├── test_concurrent.py     Nhóm 4: Concurrent (6 TC)
│   └── test_ui_juice_shop.py  UI Tests (Playwright)
├── data/test_data_deadlock.xlsx
├── conftest.py / pytest.ini
├── docker-compose.yml
└── run_tests.sh
```

## Chạy tests

```bash
# Theo nhóm
pytest -m valid_path    -v   # Nhóm 1
pytest -m deadlock_path -v   # Nhóm 2
pytest -m boundary      -v   # Nhóm 3
pytest -m concurrent    -v   # Nhóm 4
pytest -m fsm_only      -v   # Tất cả FSM (không cần browser)
pytest -m ui            -v   # UI tests (cần Juice Shop)

# Với report
pytest -m fsm_only --html=reports/report.html --self-contained-html -v
pytest -m fsm_only --alluredir=reports/allure -v && allure serve reports/allure
```

## Kết quả kỳ vọng

| Nhóm | TC | Kết quả |
|------|----|---------|
| Valid Path | 10 | PASS |
| Deadlock Path | 8 | DEADLOCK_DETECTED |
| Boundary | 8 | PASS |
| Concurrent | 6 | 4 PASS + 2 DEADLOCK_DETECTED |

Thuộc tính kiểm chứng: `AG(¬deadlock)` — không bao giờ đạt S6.

## FSM Diagram

```
S0(Guest) → S1(Auth) → S2(Cart) → S3(Checkout) → S4(Processing) → S5(Confirmed✓)
                                        │                │
                                     deadlock          deadlock
                                        ↓                ↓
                                    S6(Deadlock✗)   S6(Deadlock✗)

S1/S2/S3/S4 --session_expire--> S7(Expired) --restore--> S0
```

## Docker — Juice Shop

```bash
docker compose up -d juice-shop     # Khởi động
docker compose down                 # Dừng
docker compose --profile full-test up  # Chạy test trong Docker
```

Juice Shop chạy tại: http://localhost:3000  
Admin: `admin@juice-sh.op` / `admin123`

## Reports (sinh tự động sau khi chạy)

- `reports/test_report_*.html` — HTML report
- `reports/test_results_*.xlsx` — Excel kết quả
- `reports/counterexamples_*.json` — Counterexample JSON

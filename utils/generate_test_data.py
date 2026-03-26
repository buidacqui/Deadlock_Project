"""
utils/generate_test_data.py
============================
Tự động sinh file Excel test_data_deadlock.xlsx với 4 sheet DDT.
Chạy một lần để tạo dữ liệu: python utils/generate_test_data.py
"""

import pandas as pd
from pathlib import Path
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter

OUTPUT_FILE = Path(__file__).parent.parent / "data" / "test_data_deadlock.xlsx"

# ─── Sheet 1: Valid Path (10 TC) ────────────────────────────
VALID_PATH = [
    {
        "TC_ID": "VP_001",
        "Description": "Luồng hoàn chỉnh: đăng nhập → thêm 1 sp → checkout → thanh toán → xác nhận",
        "Init_State": "guest",
        "Event_Sequence": "do_login,do_add_to_cart,do_checkout,do_pay,do_confirm",
        "Expected_State": "confirmed",
        "Is_Deadlock": False,
        "Expected_Result": "PASS",
        "Notes": "Happy path cơ bản",
    },
    {
        "TC_ID": "VP_002",
        "Description": "Thêm 2 sản phẩm trước khi checkout",
        "Init_State": "guest",
        "Event_Sequence": "do_login,do_add_to_cart,do_add_to_cart,do_checkout,do_pay,do_confirm",
        "Expected_State": "confirmed",
        "Is_Deadlock": False,
        "Expected_Result": "PASS",
        "Notes": "Multiple items in cart",
    },
    {
        "TC_ID": "VP_003",
        "Description": "Login → add sp → cancel → add lại → checkout → pay → confirm",
        "Init_State": "guest",
        "Event_Sequence": "do_login,do_add_to_cart,do_cancel,do_add_to_cart,do_checkout,do_pay,do_confirm",
        "Expected_State": "confirmed",
        "Is_Deadlock": False,
        "Expected_Result": "PASS",
        "Notes": "Cancel giỏ rồi thêm lại",
    },
    {
        "TC_ID": "VP_004",
        "Description": "Payment fail rồi retry thành công",
        "Init_State": "guest",
        "Event_Sequence": "do_login,do_add_to_cart,do_checkout,do_pay,do_pay_fail,do_pay,do_confirm",
        "Expected_State": "confirmed",
        "Is_Deadlock": False,
        "Expected_Result": "PASS",
        "Notes": "Retry sau payment fail",
    },
    {
        "TC_ID": "VP_005",
        "Description": "Thêm 3 sản phẩm, checkout, xác nhận đơn hàng",
        "Init_State": "guest",
        "Event_Sequence": "do_login,do_add_to_cart,do_add_to_cart,do_add_to_cart,do_checkout,do_pay,do_confirm",
        "Expected_State": "confirmed",
        "Is_Deadlock": False,
        "Expected_Result": "PASS",
        "Notes": "3 items",
    },
    {
        "TC_ID": "VP_006",
        "Description": "Hủy checkout rồi vào lại checkout",
        "Init_State": "guest",
        "Event_Sequence": "do_login,do_add_to_cart,do_checkout,do_cancel,do_checkout,do_pay,do_confirm",
        "Expected_State": "confirmed",
        "Is_Deadlock": False,
        "Expected_Result": "PASS",
        "Notes": "Cancel checkout rồi vào lại",
    },
    {
        "TC_ID": "VP_007",
        "Description": "Luồng đầy đủ với empty cart check trước",
        "Init_State": "guest",
        "Event_Sequence": "do_login,do_add_to_cart,do_empty_cart,do_add_to_cart,do_checkout,do_pay,do_confirm",
        "Expected_State": "confirmed",
        "Is_Deadlock": False,
        "Expected_Result": "PASS",
        "Notes": "Empty rồi add lại",
    },
    {
        "TC_ID": "VP_008",
        "Description": "Payment fail 2 lần rồi thành công",
        "Init_State": "guest",
        "Event_Sequence": "do_login,do_add_to_cart,do_checkout,do_pay,do_pay_fail,do_pay,do_pay_fail,do_pay,do_confirm",
        "Expected_State": "confirmed",
        "Is_Deadlock": False,
        "Expected_Result": "PASS",
        "Notes": "2 lần retry",
    },
    {
        "TC_ID": "VP_009",
        "Description": "Nhiều lần cancel và thêm sản phẩm",
        "Init_State": "guest",
        "Event_Sequence": "do_login,do_add_to_cart,do_cancel,do_add_to_cart,do_checkout,do_pay,do_confirm",
        "Expected_State": "confirmed",
        "Is_Deadlock": False,
        "Expected_Result": "PASS",
        "Notes": "Multiple cancel",
    },
    {
        "TC_ID": "VP_010",
        "Description": "Luồng nhanh nhất có thể",
        "Init_State": "guest",
        "Event_Sequence": "do_login,do_add_to_cart,do_checkout,do_pay,do_confirm",
        "Expected_State": "confirmed",
        "Is_Deadlock": False,
        "Expected_Result": "PASS",
        "Notes": "Minimal steps",
    },
]

# ─── Sheet 2: Deadlock Path (8 TC) ──────────────────────────
DEADLOCK_PATH = [
    {
        "TC_ID": "DL_001",
        "Description": "2 session cùng checkout cùng order → circular wait",
        "Init_State": "guest",
        "Event_Sequence": "do_login,do_add_to_cart,do_checkout,do_deadlock",
        "Expected_State": "deadlock",
        "Is_Deadlock": True,
        "Expected_Result": "DEADLOCK_DETECTED",
        "Notes": "Concurrent checkout scenario S3→S6",
    },
    {
        "TC_ID": "DL_002",
        "Description": "Block payment → retry liên tục → deadlock",
        "Init_State": "guest",
        "Event_Sequence": "do_login,do_add_to_cart,do_checkout,do_pay,do_deadlock",
        "Expected_State": "deadlock",
        "Is_Deadlock": True,
        "Expected_Result": "DEADLOCK_DETECTED",
        "Notes": "Processing state deadlock S4→S6",
    },
    {
        "TC_ID": "DL_003",
        "Description": "Session A lock resource, Session B đang chờ A trong checkout",
        "Init_State": "guest",
        "Event_Sequence": "do_login,do_add_to_cart,do_checkout,do_deadlock",
        "Expected_State": "deadlock",
        "Is_Deadlock": True,
        "Expected_Result": "DEADLOCK_DETECTED",
        "Notes": "Resource lock scenario",
    },
    {
        "TC_ID": "DL_004",
        "Description": "Nhiều retry payment tạo deadlock trong processing",
        "Init_State": "guest",
        "Event_Sequence": "do_login,do_add_to_cart,do_checkout,do_pay,do_pay_fail,do_pay,do_deadlock",
        "Expected_State": "deadlock",
        "Is_Deadlock": True,
        "Expected_Result": "DEADLOCK_DETECTED",
        "Notes": "Retry loop → deadlock",
    },
    {
        "TC_ID": "DL_005",
        "Description": "2 session tranh chấp payment gateway cùng lúc",
        "Init_State": "guest",
        "Event_Sequence": "do_login,do_add_to_cart,do_checkout,do_pay,do_deadlock",
        "Expected_State": "deadlock",
        "Is_Deadlock": True,
        "Expected_Result": "DEADLOCK_DETECTED",
        "Notes": "Payment gateway race condition",
    },
    {
        "TC_ID": "DL_006",
        "Description": "Circular wait: A chờ B, B chờ C, C chờ A",
        "Init_State": "guest",
        "Event_Sequence": "do_login,do_add_to_cart,do_checkout,do_deadlock",
        "Expected_State": "deadlock",
        "Is_Deadlock": True,
        "Expected_Result": "DEADLOCK_DETECTED",
        "Notes": "3-session circular wait",
    },
    {
        "TC_ID": "DL_007",
        "Description": "Double lock trên cart trong concurrent add-to-cart",
        "Init_State": "guest",
        "Event_Sequence": "do_login,do_add_to_cart,do_checkout,do_deadlock",
        "Expected_State": "deadlock",
        "Is_Deadlock": True,
        "Expected_Result": "DEADLOCK_DETECTED",
        "Notes": "Cart lock deadlock",
    },
    {
        "TC_ID": "DL_008",
        "Description": "Session A giữ lock S3, không release, B timeout rồi cả hai deadlock",
        "Init_State": "guest",
        "Event_Sequence": "do_login,do_add_to_cart,do_checkout,do_pay,do_deadlock",
        "Expected_State": "deadlock",
        "Is_Deadlock": True,
        "Expected_Result": "DEADLOCK_DETECTED",
        "Notes": "Lock not released",
    },
]

# ─── Sheet 3: Boundary State (8 TC) ─────────────────────────
BOUNDARY_STATE = [
    {
        "TC_ID": "BD_001",
        "Description": "Checkout với giỏ hàng rỗng (không có sản phẩm)",
        "Init_State": "guest",
        "Event_Sequence": "do_login,do_add_to_cart,do_empty_cart",
        "Expected_State": "cart_active",
        "Is_Deadlock": False,
        "Expected_Result": "PASS",
        "Notes": "Cart rỗng → không thể checkout, giữ ở cart_active",
    },
    {
        "TC_ID": "BD_002",
        "Description": "Session hết hạn tại bước checkout",
        "Init_State": "guest",
        "Event_Sequence": "do_login,do_add_to_cart,do_checkout,do_session_expire,do_restore",
        "Expected_State": "guest",
        "Is_Deadlock": False,
        "Expected_Result": "PASS",
        "Notes": "Session expire tại S3 → S7 → S0, không S6",
    },
    {
        "TC_ID": "BD_003",
        "Description": "Session hết hạn tại bước processing",
        "Init_State": "guest",
        "Event_Sequence": "do_login,do_add_to_cart,do_checkout,do_pay,do_session_expire,do_restore",
        "Expected_State": "guest",
        "Is_Deadlock": False,
        "Expected_Result": "PASS",
        "Notes": "Session expire tại S4 → S7 → S0",
    },
    {
        "TC_ID": "BD_004",
        "Description": "Đăng nhập sai mật khẩu nhiều lần",
        "Init_State": "guest",
        "Event_Sequence": "do_login_fail,do_login_fail,do_login_fail,do_login",
        "Expected_State": "authenticated",
        "Is_Deadlock": False,
        "Expected_Result": "PASS",
        "Notes": "3 lần fail rồi thành công, không deadlock",
    },
    {
        "TC_ID": "BD_005",
        "Description": "Session expire tại cart_active rồi khôi phục",
        "Init_State": "guest",
        "Event_Sequence": "do_login,do_add_to_cart,do_session_expire,do_restore",
        "Expected_State": "guest",
        "Is_Deadlock": False,
        "Expected_Result": "PASS",
        "Notes": "S2 expire → S7 → S0",
    },
    {
        "TC_ID": "BD_006",
        "Description": "Cancel ngay khi vừa vào checkout",
        "Init_State": "guest",
        "Event_Sequence": "do_login,do_add_to_cart,do_checkout,do_cancel",
        "Expected_State": "cart_active",
        "Is_Deadlock": False,
        "Expected_Result": "PASS",
        "Notes": "Cancel checkout → về cart_active",
    },
    {
        "TC_ID": "BD_007",
        "Description": "Nhiều lần session expire liên tiếp",
        "Init_State": "guest",
        "Event_Sequence": "do_login,do_session_expire,do_restore,do_login,do_add_to_cart,do_checkout,do_pay,do_confirm",
        "Expected_State": "confirmed",
        "Is_Deadlock": False,
        "Expected_Result": "PASS",
        "Notes": "Expire rồi login lại, hoàn thành bình thường",
    },
    {
        "TC_ID": "BD_008",
        "Description": "Payment fail nhiều lần nhưng không deadlock",
        "Init_State": "guest",
        "Event_Sequence": "do_login,do_add_to_cart,do_checkout,do_pay,do_pay_fail,do_pay,do_pay_fail,do_pay,do_pay_fail,do_pay,do_confirm",
        "Expected_State": "confirmed",
        "Is_Deadlock": False,
        "Expected_Result": "PASS",
        "Notes": "3 lần fail → succeed, không phải deadlock",
    },
]

# ─── Sheet 4: Concurrent (6 TC) ─────────────────────────────
CONCURRENT = [
    {
        "TC_ID": "CC_001",
        "Description": "2 session checkout song song cùng order_id → circular wait",
        "Init_State": "guest",
        "Event_Sequence": "CONCURRENT:session_a=do_login+do_add_to_cart+do_checkout,session_b=do_login+do_add_to_cart+do_checkout,conflict=same_order",
        "Expected_State": "deadlock",
        "Is_Deadlock": True,
        "Expected_Result": "DEADLOCK_DETECTED",
        "Notes": "2 sessions, 1 order — circular wait tại S3",
    },
    {
        "TC_ID": "CC_002",
        "Description": "Session A giữ S3, B phải chờ → B timeout → không circular wait",
        "Init_State": "guest",
        "Event_Sequence": "CONCURRENT:session_a=do_login+do_add_to_cart+do_checkout,session_b=do_login+do_add_to_cart+do_checkout+do_session_expire+do_restore,conflict=different_orders",
        "Expected_State": "guest",
        "Is_Deadlock": False,
        "Expected_Result": "PASS",
        "Notes": "B timeout thoát ra, không deadlock",
    },
    {
        "TC_ID": "CC_003",
        "Description": "3 session, circular wait A→B→C→A",
        "Init_State": "guest",
        "Event_Sequence": "CONCURRENT:session_a=do_login+do_add_to_cart+do_checkout,session_b=do_login+do_add_to_cart+do_checkout,session_c=do_login+do_add_to_cart+do_checkout,conflict=circular_3",
        "Expected_State": "deadlock",
        "Is_Deadlock": True,
        "Expected_Result": "DEADLOCK_DETECTED",
        "Notes": "3-session circular wait",
    },
    {
        "TC_ID": "CC_004",
        "Description": "2 session checkout các order khác nhau — không deadlock",
        "Init_State": "guest",
        "Event_Sequence": "CONCURRENT:session_a=do_login+do_add_to_cart+do_checkout+do_pay+do_confirm,session_b=do_login+do_add_to_cart+do_checkout+do_pay+do_confirm,conflict=no_conflict",
        "Expected_State": "confirmed",
        "Is_Deadlock": False,
        "Expected_Result": "PASS",
        "Notes": "Independent orders, no deadlock",
    },
    {
        "TC_ID": "CC_005",
        "Description": "Session A lock payment gateway, B chờ → A fail → B tiếp tục",
        "Init_State": "guest",
        "Event_Sequence": "CONCURRENT:session_a=do_login+do_add_to_cart+do_checkout+do_pay+do_pay_fail,session_b=do_login+do_add_to_cart+do_checkout+do_pay+do_confirm,conflict=no_conflict",
        "Expected_State": "confirmed",
        "Is_Deadlock": False,
        "Expected_Result": "PASS",
        "Notes": "A fail → B không bị block mãi",
    },
    {
        "TC_ID": "CC_006",
        "Description": "2 session, A deadlock, B vẫn hoàn thành bình thường",
        "Init_State": "guest",
        "Event_Sequence": "CONCURRENT:session_a=do_login+do_add_to_cart+do_checkout+do_deadlock,session_b=do_login+do_add_to_cart+do_checkout+do_pay+do_confirm,conflict=isolated",
        "Expected_State": "confirmed",
        "Is_Deadlock": False,
        "Expected_Result": "PASS",
        "Notes": "Deadlock isolated — B không bị ảnh hưởng",
    },
]


def apply_excel_styles(ws, header_fill_hex: str = "3C3489"):
    """Áp dụng style đẹp cho worksheet."""
    from openpyxl.styles import PatternFill, Font, Alignment, Border, Side

    header_fill = PatternFill(start_color=header_fill_hex, end_color=header_fill_hex, fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=11)
    thin = Side(style="thin", color="CCCCCC")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    for col_idx, cell in enumerate(ws[1], 1):
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = border

    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.border = border
            cell.alignment = Alignment(vertical="center", wrap_text=True)
            if cell.row % 2 == 0:
                cell.fill = PatternFill(start_color="F5F5F0", end_color="F5F5F0", fill_type="solid")

    # Auto-fit column widths
    for col in ws.columns:
        max_len = max((len(str(cell.value)) if cell.value else 0) for cell in col)
        ws.column_dimensions[get_column_letter(col[0].column)].width = min(max_len + 4, 50)

    ws.row_dimensions[1].height = 20
    ws.freeze_panes = "A2"


def generate():
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    sheets = {
        "Valid_Path":      VALID_PATH,
        "Deadlock_Path":   DEADLOCK_PATH,
        "Boundary_State":  BOUNDARY_STATE,
        "Concurrent":      CONCURRENT,
    }

    colors = {
        "Valid_Path":     "0F6E56",
        "Deadlock_Path":  "A32D2D",
        "Boundary_State": "854F0B",
        "Concurrent":     "3C3489",
    }

    with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
        for sheet_name, data in sheets.items():
            df = pd.DataFrame(data)
            df.to_excel(writer, sheet_name=sheet_name, index=False)
            ws = writer.sheets[sheet_name]
            apply_excel_styles(ws, colors[sheet_name])

    print(f"✓ Test data generated: {OUTPUT_FILE}")
    total = sum(len(d) for d in sheets.values())
    for name, data in sheets.items():
        print(f"  • {name}: {len(data)} test cases")
    print(f"  Total: {total} test cases")


if __name__ == "__main__":
    generate()

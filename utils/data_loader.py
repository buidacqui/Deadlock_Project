"""
utils/data_loader.py
====================
Đọc Test Data từ file Excel theo phương pháp Data-Driven Testing (DDT).
Tách biệt hoàn toàn Test Code và Test Data.
Hỗ trợ 4 sheet: Valid_Path, Deadlock_Path, Boundary_State, Concurrent.
"""

import pandas as pd
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DATA_FILE = Path(__file__).parent.parent / "data" / "test_data_deadlock.xlsx"

SHEET_NAMES = {
    "valid":      "Valid_Path",
    "deadlock":   "Deadlock_Path",
    "boundary":   "Boundary_State",
    "concurrent": "Concurrent",
}

REQUIRED_COLUMNS = [
    "TC_ID",
    "Description",
    "Init_State",
    "Event_Sequence",
    "Expected_State",
    "Is_Deadlock",
    "Expected_Result",
]


class DataLoader:
    """
    Đọc và validate dữ liệu kiểm thử từ Excel.
    """

    def __init__(self, filepath: Optional[Path] = None):
        self.filepath = filepath or DATA_FILE

    def load_sheet(self, sheet_key: str) -> list[dict]:
        """
        Load một sheet Excel thành list of dict.

        Args:
            sheet_key: 'valid' | 'deadlock' | 'boundary' | 'concurrent'

        Returns:
            List các test case dưới dạng dict
        """
        sheet_name = SHEET_NAMES.get(sheet_key)
        if not sheet_name:
            raise ValueError(f"Unknown sheet key: '{sheet_key}'. Valid: {list(SHEET_NAMES.keys())}")

        if not self.filepath.exists():
            raise FileNotFoundError(
                f"Test data file not found: {self.filepath}\n"
                "Hãy chạy: python utils/generate_test_data.py"
            )

        try:
            df = pd.read_excel(self.filepath, sheet_name=sheet_name)
        except Exception as e:
            raise RuntimeError(f"Cannot read sheet '{sheet_name}': {e}")

        df = df.dropna(how="all")
        self._validate_columns(df, sheet_name)
        self._normalize(df)

        records = df.to_dict(orient="records")
        logger.info(f"Loaded {len(records)} test cases from sheet '{sheet_name}'")
        return records

    def _validate_columns(self, df: pd.DataFrame, sheet_name: str):
        missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(
                f"Sheet '{sheet_name}' thiếu các cột: {missing}\n"
                f"Cột hiện có: {list(df.columns)}"
            )

    def _normalize(self, df: pd.DataFrame):
        """Chuẩn hóa kiểu dữ liệu."""
        df["Is_Deadlock"] = df["Is_Deadlock"].astype(str).str.upper().map(
            {"TRUE": True, "FALSE": False, "1": True, "0": False}
        ).fillna(False)

        df["TC_ID"]           = df["TC_ID"].astype(str).str.strip()
        df["Event_Sequence"]  = df["Event_Sequence"].astype(str).str.strip()
        df["Expected_State"]  = df["Expected_State"].astype(str).str.strip()
        df["Expected_Result"] = df["Expected_Result"].astype(str).str.strip()
        df["Init_State"]      = df["Init_State"].astype(str).str.strip()

    def parse_events(self, event_sequence_str: str) -> list[str]:
        """
        Parse chuỗi sự kiện từ Excel thành list.
        Ví dụ: "do_login,do_add_to_cart,do_checkout" → ["do_login", "do_add_to_cart", "do_checkout"]
        """
        if not event_sequence_str or event_sequence_str.lower() == "nan":
            return []
        return [e.strip() for e in event_sequence_str.split(",") if e.strip()]

    def load_all(self) -> dict[str, list[dict]]:
        """Load tất cả 4 sheet."""
        return {key: self.load_sheet(key) for key in SHEET_NAMES}

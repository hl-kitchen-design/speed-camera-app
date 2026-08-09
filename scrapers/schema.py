"""共用資料型別與違規類型文字辨識工具，給所有 scraper 共用。"""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass

VALID_TYPES: set[str] = {
    "speed",
    "red_light",
    "yield_pedestrian",
    "illegal_turn",
    "two_stage_turn",
    "bus_lane",
    "keep_clear",
    "illegal_parking",
    "cross_double_line",
    "restricted_lane",
}

# 順序不影響比對結果（每個關鍵字獨立檢查、全部收集），
# 但關鍵字要夠具體，避免短關鍵字誤配到不相關的描述
# （例如不能只用「轉彎」去比對「轉彎車占用直行車道」）。
_TYPE_KEYWORDS: list[tuple[str, str]] = [
    ("不停讓行人", "yield_pedestrian"),
    ("未停讓行人", "yield_pedestrian"),
    ("不依規定讓", "yield_pedestrian"),
    ("紅燈右轉", "red_light"),
    ("紅燈越線", "red_light"),
    ("闖紅燈", "red_light"),
    ("違規(臨時)停車", "illegal_parking"),
    ("違規臨時停車", "illegal_parking"),
    ("違規停車", "illegal_parking"),
    ("違規上、下客", "illegal_parking"),
    ("違規攬客", "illegal_parking"),
    ("跨越雙白線", "cross_double_line"),
    ("跨越雙黃線", "cross_double_line"),
    ("行駛人行道", "restricted_lane"),
    ("禁行路段", "restricted_lane"),
    ("禁行車種", "restricted_lane"),
    ("公車專用道", "bus_lane"),
    ("兩段式左轉", "two_stage_turn"),
    ("路口淨空", "keep_clear"),
    ("違規迴轉", "illegal_turn"),
    ("未依標誌標線", "illegal_turn"),
    ("不依標誌標線", "illegal_turn"),
    ("轉彎未依規定", "illegal_turn"),
    ("違規轉彎", "illegal_turn"),
    ("超速", "speed"),
]


def classify_types(text: str) -> list[str]:
    """從中文違規描述文字辨識違規類型，回傳依原文出現順序去重的 canonical type 清單。
    關鍵字清單無法涵蓋所有縣市用語，辨識不到時回傳空清單，不會拋錯。"""
    first_index: dict[str, int] = {}
    for keyword, canonical in _TYPE_KEYWORDS:
        idx = text.find(keyword)
        if idx == -1:
            continue
        if canonical not in first_index or idx < first_index[canonical]:
            first_index[canonical] = idx
    return [canonical for canonical, _ in sorted(first_index.items(), key=lambda kv: kv[1])]


def make_id(source_name: str, address: str) -> str:
    """用來源名稱+地址算出穩定的短 id，同一筆資料多次執行結果一致。"""
    raw = f"{source_name}|{address}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]


@dataclass
class EnforcementPoint:
    id: str
    county: str
    district: str
    address: str
    lat: float | None
    lng: float | None
    violation_types: list[str]
    source_name: str
    source_url: str
    data_quality: str  # "coords" | "geocoded" | "district-centroid" | "no-coords"
    fetched_at: str

    def to_dict(self) -> dict:
        return asdict(self)

"""通用 HTML 表格擷取器，給新竹/高雄/新北三個「只有網頁表格、沒有正式開放資料集」的
縣市 scraper 共用。用「表頭是否等於 expected_header（去空白後比對）」來找出資料表格，
可以合併同一頁裡多個共用表頭的子表格（例如新北市警局頁面有 5 個子表格）。"""
from __future__ import annotations

import re

import requests
from bs4 import BeautifulSoup


def _normalize(s: str) -> str:
    return re.sub(r"\s+", "", s)


def fetch_html_table_rows(
    url: str, expected_header: list[str], verify_ssl: bool = True
) -> list[dict[str, str]]:
    resp = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; speed-camera-app-scraper/1.0)"},
        timeout=20,
        verify=verify_ssl,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    normalized_header = [_normalize(h) for h in expected_header]
    rows_out: list[dict[str, str]] = []

    for table in soup.find_all("table"):
        in_data_section = False
        for row in table.find_all("tr"):
            cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
            if not cells:
                continue
            if [_normalize(c) for c in cells] == normalized_header:
                in_data_section = True
                continue
            if in_data_section and len(cells) == len(expected_header):
                rows_out.append(dict(zip(expected_header, cells)))

    return rows_out

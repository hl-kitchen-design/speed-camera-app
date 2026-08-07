import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from publish import _abort_if_empty, _fetch_all, build_output
from schema import EnforcementPoint


def _point(pid: str) -> EnforcementPoint:
    return EnforcementPoint(
        id=pid,
        county="測試縣市",
        district="",
        address="測試地址",
        lat=25.0,
        lng=121.0,
        violation_types=["speed"],
        source_name="測試來源",
        source_url="https://example.com",
        data_quality="coords",
        fetched_at="2026-08-07T00:00:00Z",
    )


def test_build_output_has_four_keys():
    output = build_output([_point("a"), _point("b")])
    assert set(output.keys()) == {"points", "parking", "sections", "version"}


def test_build_output_points_are_dicts():
    output = build_output([_point("a")])
    assert output["points"][0]["id"] == "a"


def test_build_output_parking_and_sections_are_empty():
    output = build_output([_point("a")])
    assert output["parking"] == []
    assert output["sections"] == []


def test_build_output_version_counts():
    output = build_output([_point("a"), _point("b")])
    assert output["version"]["point_count"] == 2
    assert output["version"]["parking_count"] == 0
    assert output["version"]["section_count"] == 0
    assert "data_version" in output["version"]


def test_build_output_dedupes_points_with_same_id():
    # 2026-08-07 實跑真實管線發現：高雄市/新北市網頁的原始 HTML 裡同一份表格
    # 重複出現兩次（很可能是響應式版面把「手機版/桌機版」表格都寫進同一份 HTML，
    # 只靠 CSS 隱藏其中一份，但 BeautifulSoup 不理會 CSS），導致每筆資料被抓兩次，
    # 兩次結果的 id 完全相同（make_id 是內容決定的雜湊）。build_output 要在合併時
    # 依 id 去重，只保留第一筆，不能整批原封不動塞進輸出。
    output = build_output([_point("a"), _point("a"), _point("b")])
    assert len(output["points"]) == 2
    assert output["version"]["point_count"] == 2
    assert {p["id"] for p in output["points"]} == {"a", "b"}


class _FakeModule:
    """假造一個有 fetch() 的 module 物件，模擬單一資料源掛掉的情況。"""

    def __init__(self, name: str, fetch_fn):
        self.__name__ = name
        self._fetch_fn = fetch_fn

    def fetch(self):
        return self._fetch_fn()


def test_fetch_all_skips_source_that_raises_and_keeps_others():
    # 2026-08-07 排程實跑發現：新竹市網站在 GitHub Actions 的雲端機房連線逾時，
    # 會讓整條管線中斷、其他 6 個原本能成功的來源也全部作廢。_fetch_all 要在
    # 單一來源丟例外時印出訊息並跳過，繼續處理下一個來源，不能整批中斷。
    good_a = _FakeModule("good_a", lambda: [_point("a")])
    broken = _FakeModule("broken", lambda: (_ for _ in ()).throw(Exception("連線逾時")))
    good_b = _FakeModule("good_b", lambda: [_point("b")])

    points = _fetch_all([good_a, broken, good_b])

    assert {p.id for p in points} == {"a", "b"}


def test_fetch_all_all_sources_broken_returns_empty_list():
    broken_a = _FakeModule("broken_a", lambda: (_ for _ in ()).throw(Exception("boom")))
    broken_b = _FakeModule("broken_b", lambda: (_ for _ in ()).throw(Exception("boom")))

    points = _fetch_all([broken_a, broken_b])

    assert points == []


def test_abort_if_empty_exits_with_nonzero_status_when_no_points():
    # 2026-08-07 Task 12 review 發現：_fetch_all 的容錯機制拿掉了一個原本意外存在的
    # 安全網——以前「全部來源都失敗」會讓整個程式直接 crash，GitHub Actions 因此
    # 不會走到後面 commit/push 的步驟，不會把 gh-pages 上原本好好的資料蓋成空的。
    # 現在改成 try/except 吃掉例外之後，若沒有這個明確的檢查，全部來源失敗時
    # build_output([]) 會產出「看起來合法」但是空的 JSON，還是會被正常發布出去，
    # 蓋掉舊資料。這裡補一個明確的中止檢查，不能只靠 _fetch_all 本身。
    with pytest.raises(SystemExit) as exc_info:
        _abort_if_empty([])
    assert exc_info.value.code != 0


def test_abort_if_empty_does_nothing_when_points_exist():
    _abort_if_empty([_point("a")])  # 不應該拋出任何例外

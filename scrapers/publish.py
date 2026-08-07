"""合併 7 個資料源的輸出，寫成 points.json / parking.json / sections.json / version.json，
放進 gh-pages/ 目錄（GitHub Actions 會把這個目錄的內容 commit 到 gh-pages 分支）。
parking.json / sections.json 目前固定是空陣列——沒有任何資料源支援
ParkingEnforcement（違停計時門檻）或 SectionSpeedZone（區間測速路段座標序列）的欄位，
見 docs/superpowers/specs/2026-08-05-speed-camera-app-design.md 第 11 節已知限制。"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from schema import EnforcementPoint

# 用 abspath 而非單純 os.path.dirname(__file__)：後者在 __file__ 是相對路徑時
# （例如用 `python publish.py` 從 scrapers/ 目錄內執行）算出來的結果會依執行時的
# 工作目錄而變化。用 abspath 固定成「不管從哪裡呼叫，輸出目錄永遠是 scrapers/ 的上一層」，
# 也就是 repo 根目錄下的 gh-pages-build/（跟 scrapers/ 同一層，不是 scrapers/gh-pages-build/）。
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "gh-pages-build")


def _dedupe_by_id(points: list[EnforcementPoint]) -> list[EnforcementPoint]:
    # 2026-08-07 實跑真實管線發現：高雄市/新北市網頁的原始 HTML 裡同一份表格重複出現
    # 兩次（響應式版面常見的手機版/桌機版都寫進同一份 HTML、只靠 CSS 隱藏其中一份，
    # BeautifulSoup 不理會 CSS），導致每筆資料被抓兩次，且兩次的 id 完全相同
    # （make_id 是內容決定的雜湊）。這裡依 id 去重，只保留第一次出現的那筆。
    seen: set[str] = set()
    deduped: list[EnforcementPoint] = []
    for point in points:
        if point.id in seen:
            continue
        seen.add(point.id)
        deduped.append(point)
    return deduped


def build_output(all_points: list[EnforcementPoint]) -> dict:
    deduped_points = _dedupe_by_id(all_points)
    version = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return {
        "points": [p.to_dict() for p in deduped_points],
        "parking": [],
        "sections": [],
        "version": {
            "data_version": version,
            "point_count": len(deduped_points),
            "parking_count": 0,
            "section_count": 0,
        },
    }


def _fetch_all(modules) -> list[EnforcementPoint]:
    # 排程自動化要預期「某個政府網站當下連不上」是常態（例如國外雲端機房連台灣
    # 地方政府網站可能被防火牆擋掉 connect timeout），單一來源失敗不該讓其他
    # 原本能成功的來源也全部作廢、什麼都不發布。這裡先求「壞掉不拖垮全部」，
    # 不做重試/backoff。
    all_points: list[EnforcementPoint] = []
    for module in modules:
        try:
            points = module.fetch()
        except Exception as e:
            print(f"{module.__name__}: 抓取失敗，略過此來源。錯誤：{e}")
            continue
        print(f"{module.__name__}: {len(points)} 筆")
        all_points.extend(points)
    return all_points


def main() -> None:
    import hsinchu
    import kaohsiung
    import national_speed
    import new_taipei
    import taichung
    import tainan
    import taipei

    all_points = _fetch_all(
        (national_speed, taichung, taipei, tainan, hsinchu, kaohsiung, new_taipei)
    )

    output = build_output(all_points)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for name in ("points", "parking", "sections"):
        with open(os.path.join(OUTPUT_DIR, f"{name}.json"), "w", encoding="utf-8") as f:
            json.dump(output[name], f, ensure_ascii=False, indent=2)
    with open(os.path.join(OUTPUT_DIR, "version.json"), "w", encoding="utf-8") as f:
        json.dump(output["version"], f, ensure_ascii=False, indent=2)

    print(f"總計 {len(all_points)} 筆，輸出到 {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

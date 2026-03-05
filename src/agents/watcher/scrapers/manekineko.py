"""
Agent Watcher - カラオケまねきねこ 店舗スクレイパー
=====================================================
大阪府のカラオケまねきねこ店舗情報を取得する。

ターゲット: https://www.karaokemanekineko.jp/locations/osaka/
「もっとみる」ボタンで遅延読み込みされる店舗を全件取得する。

使い方:
    python agent_watcher/scrapers/manekineko.py
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PwTimeoutError


# =====================================================
# 定数
# =====================================================
BASE_URL = "https://www.karaokemanekineko.jp/locations/osaka/"
OUTPUT_DIR = "data"


def extract_station_from_address(address: str) -> str:
    """
    住所から最寄り駅を推定する（簡易版）。

    まねきねこのページには駅名データが直接含まれないため、
    住所の市区町村部分を返す。後で normalizer が正規化する。

    Args:
        address: 住所文字列（例: "大阪府 大阪市 中央区難波1-8-16 3F"）

    Returns:
        推定エリア文字列
    """
    if not address:
        return ""

    # 全角スペースも半角に統一
    addr = address.replace("\u3000", " ").strip()

    # "大阪府 大阪市 中央区難波1-8-16 3F" → "中央区難波"
    # "大阪府 堺市 北区中百舌鳥町2-23" → "北区中百舌鳥町"
    parts = addr.split()
    if len(parts) >= 3:
        # 3つ目が "区" を含む場合（大阪市内）
        return parts[2] if len(parts) >= 3 else ""
    return ""


def normalize_branch_name(raw_name: str) -> str:
    """
    支店名を正規化する。

    Args:
        raw_name: 生の支店名（例: "なんばＨＩＰＳ店"）

    Returns:
        正規化された店舗名
    """
    # 全角英数字を半角に変換
    name = raw_name
    name = name.translate(str.maketrans(
        "ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ０１２３４５６７８９",
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    ))
    return f"カラオケまねきねこ {name}"


def scrape_manekineko() -> list[dict]:
    """
    まねきねこ大阪府の店舗一覧をスクレイピングする。

    Returns:
        店舗データのリスト
    """
    stores = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        page = context.new_page()

        print(f"アクセス中: {BASE_URL}", file=sys.stderr)
        page.goto(BASE_URL, wait_until="networkidle", timeout=30000)

        # Cookie バナーを閉じる
        try:
            cookie_btn = page.locator(".cc-btn.cc-dismiss, .cc-compliance .cc-btn")
            if cookie_btn.count() > 0:
                cookie_btn.first.click()
                page.wait_for_timeout(500)
        except Exception:
            pass

        # 「もっとみる」ボタンをクリックして全店舗を読み込む
        print("全店舗を読み込み中...", file=sys.stderr)
        click_count = 0
        while True:
            try:
                show_more = page.locator("#js-show-more")
                if show_more.count() == 0 or not show_more.is_visible():
                    break
                show_more.click()
                click_count += 1
                page.wait_for_timeout(1000)
            except PwTimeoutError:
                break
            except Exception:
                break

            # 安全のため最大20回
            if click_count >= 20:
                break

        if click_count > 0:
            print(f"  「もっとみる」を {click_count} 回クリック", file=sys.stderr)

        # 店舗要素を取得
        store_elements = page.locator(".js-store")
        total = store_elements.count()
        print(f"検出された店舗数: {total}", file=sys.stderr)

        for i in range(total):
            try:
                el = store_elements.nth(i)

                # 店名
                name_el = el.locator(".content__unit-ttl__branch")
                branch_name = name_el.text_content().strip() if name_el.count() > 0 else ""

                # 詳細URL
                link_el = el.locator("a.content__unit-detailBtn")
                detail_url = ""
                if link_el.count() > 0:
                    href = link_el.get_attribute("href") or ""
                    if href.startswith("/"):
                        detail_url = f"https://www.karaokemanekineko.jp{href}"
                    elif href.startswith("http"):
                        detail_url = href

                # 住所
                addr_el = el.locator(".content__unit-address")
                address = addr_el.text_content().strip() if addr_el.count() > 0 else ""

                if not branch_name:
                    continue

                store_name = normalize_branch_name(branch_name)
                area_hint = extract_station_from_address(address)

                store = {
                    "chain": "manekineko",
                    "store_name": store_name,
                    "branch_name": branch_name,
                    "detail_url": detail_url,
                    "address": address,
                    "area_hint": area_hint,
                    "station_name": "",  # normalizer で推定
                }
                stores.append(store)

                print(
                    f"  [{i + 1}/{total}] {store_name} | {address}",
                    file=sys.stderr,
                )

            except Exception as e:
                print(
                    f"  [{i + 1}/{total}] エラー: {e}",
                    file=sys.stderr,
                )

        browser.close()

    return stores


def main():
    """メイン実行関数"""
    print("=" * 60, file=sys.stderr)
    print("Agent Watcher - カラオケまねきねこ 店舗スクレイピング", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    stores = scrape_manekineko()

    if not stores:
        print("エラー: 店舗が取得できませんでした。", file=sys.stderr)
        sys.exit(1)

    # 出力ファイル
    today = datetime.now().strftime("%Y%m%d")
    output_path = Path(OUTPUT_DIR)
    output_path.mkdir(parents=True, exist_ok=True)
    filepath = output_path / f"raw_manekineko_{today}.json"

    output = {
        "scraped_at": datetime.now().isoformat(),
        "chain": "manekineko",
        "source_url": BASE_URL,
        "total_stores": len(stores),
        "stores": stores,
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 完了: {len(stores)} 店舗", file=sys.stderr)
    print(f"保存先: {filepath}", file=sys.stderr)


if __name__ == "__main__":
    main()

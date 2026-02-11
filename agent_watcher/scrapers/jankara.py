"""
ジャンカラ (Jankara) 大阪店舗スクレイパー
==========================================
大阪府内のジャンカラ全店舗の情報を取得するスクレイパー。
Playwright（ヘッドレス Chromium）を使用して動的ページからデータを抽出する。

出力:
    - store_name: 店舗名
    - area: エリア名（梅田、難波・心斎橋、その他大阪市、大阪市以外）
    - station_name: 最寄り駅名（テキストから推定）
    - address: 住所
    - detail_url: 店舗詳細ページURL
    - pricing_url: 料金ページURL
"""

import asyncio
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

# ベースURL
BASE_URL = "https://jankara.ne.jp"

# 大阪エリア定義: (area_id, area_name)
OSAKA_AREAS = [
    ("9", "梅田"),
    ("10", "難波・心斎橋"),
    ("11", "その他大阪市"),
    ("12", "大阪市以外"),
]


def extract_station_name(store_name: str, address: str = "") -> str:
    """
    店舗名や住所から最寄り駅名を推定する。
    例: "ジャンカラ十三駅前店" -> "十三"
        "ジャンカラ京橋1号店" -> "京橋"
        "ジャンカラJR福島店" -> "JR福島"
    """
    # 店舗名から駅名を推定するパターン
    patterns = [
        # "〇〇駅前店", "〇〇駅東口店" などのパターン
        r"(?:ジャンカラ|スーパージャンカラ|ジャジャーンカラ)(.+?)駅(?:前|東口|西口|南口|北口)?(?:\d*号)?店",
        # "JR〇〇店" パターン
        r"(?:ジャンカラ|スーパージャンカラ)(JR.+?)(?:\d*号)?店",
        # "〇〇店" で駅名がそのまま使われているケース (京橋、梅田 etc.)
        r"(?:ジャンカラ|スーパージャンカラ)(.+?)(?:\d*号)?店",
    ]

    for pattern in patterns:
        match = re.search(pattern, store_name)
        if match:
            candidate = match.group(1).strip()
            # 不要な接頭辞・接尾辞を除去
            candidate = re.sub(r"^(セルフの方の|みんなの|ほんまに|ディープ|オールナイト|地下鉄)", "", candidate)
            # 「BAL UTAO」等ブランド名は除外
            if candidate and not re.match(r"^[A-Z\s]+$", candidate):
                return candidate

    return ""


async def scrape_area(page, area_id: str, area_name: str) -> list[dict]:
    """
    指定エリアの店舗一覧ページをスクレイピングする。

    Args:
        page: Playwright のページオブジェクト
        area_id: エリアID（URLパラメータ）
        area_name: エリア名（日本語）

    Returns:
        店舗情報の辞書リスト
    """
    url = f"{BASE_URL}/shop/result/?a={area_id}"
    stores = []

    try:
        await page.goto(url, wait_until="networkidle", timeout=30000)
        # 少し待って動的コンテンツのレンダリングを確実にする
        await page.wait_for_timeout(2000)

        # 店舗カード要素を取得（h3タグに店舗名が入っている）
        shop_cards = await page.query_selector_all(".result__shop")
        if not shop_cards:
            # 別のセレクタトライ
            shop_cards = await page.query_selector_all("[class*='shop']")

        # h3 タグから店舗情報を取得
        h3_elements = await page.query_selector_all("h3")

        for h3 in h3_elements:
            store_name = (await h3.inner_text()).strip()
            if not store_name or "ジャンカラ" not in store_name and "スーパージャンカラ" not in store_name and "ジャジャーンカラ" not in store_name:
                # ジャンカラブランド名を含まないh3はスキップ
                continue

            # h3 の中のリンクを取得
            link = await h3.query_selector("a")
            detail_url = ""
            if link:
                href = await link.get_attribute("href")
                if href:
                    detail_url = href if href.startswith("http") else f"{BASE_URL}{href}"

            # 住所を取得 (h3の親要素から探す)
            parent = await h3.evaluate_handle("el => el.closest('.result__shop') || el.parentElement")
            address = ""
            address_el = await parent.query_selector(".result__shop-address, [class*='address']")
            if address_el:
                address = (await address_el.inner_text()).strip()

            # 最寄り駅を推定
            station_name = extract_station_name(store_name, address)

            # 料金ページURL
            pricing_url = ""
            if detail_url:
                # /shop/XXX/ -> /shop/XXX/#price
                pricing_url = detail_url.rstrip("/") + "/#price"

            store_info = {
                "store_name": store_name,
                "area": area_name,
                "station_name": station_name,
                "address": address,
                "detail_url": detail_url,
                "pricing_url": pricing_url,
            }
            stores.append(store_info)

    except PlaywrightTimeout:
        print(f"  [タイムアウト] エリア '{area_name}' のページ読み込みに失敗しました", file=sys.stderr)
    except Exception as e:
        print(f"  [エラー] エリア '{area_name}': {e}", file=sys.stderr)

    return stores


async def scrape_all_osaka_stores() -> list[dict]:
    """
    大阪府内の全ジャンカラ店舗をスクレイピングする。

    Returns:
        全店舗情報の辞書リスト
    """
    all_stores = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        for area_id, area_name in OSAKA_AREAS:
            print(f"スクレイピング中: {area_name} (a={area_id})...", file=sys.stderr)
            stores = await scrape_area(page, area_id, area_name)
            print(f"  -> {len(stores)} 店舗を取得", file=sys.stderr)
            all_stores.extend(stores)

            # サーバーへの負荷軽減 - リクエスト間隔を空ける
            await page.wait_for_timeout(1500)

        await browser.close()

    return all_stores


def save_results(stores: list[dict], output_dir: str = "data") -> str:
    """
    結果をJSONファイルに保存する。

    Args:
        stores: 店舗情報リスト
        output_dir: 出力ディレクトリ

    Returns:
        保存先ファイルパス
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime("%Y%m%d")
    filename = f"raw_jankara_{date_str}.json"
    filepath = output_path / filename

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(
            {
                "chain": "ジャンカラ",
                "scraped_at": datetime.now().isoformat(),
                "total_stores": len(stores),
                "stores": stores,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    return str(filepath)


async def main():
    """メイン実行関数"""
    print("=" * 50, file=sys.stderr)
    print("ジャンカラ 大阪府内店舗スクレイパー", file=sys.stderr)
    print("=" * 50, file=sys.stderr)

    stores = await scrape_all_osaka_stores()

    if stores:
        # data/ に保存
        filepath = save_results(stores)
        print(f"\n{len(stores)} 店舗のデータを保存しました: {filepath}", file=sys.stderr)

        # JSON を標準出力にも出力
        output = json.dumps(
            {
                "chain": "ジャンカラ",
                "scraped_at": datetime.now().isoformat(),
                "total_stores": len(stores),
                "stores": stores,
            },
            ensure_ascii=False,
            indent=2,
        )
        print(output)
    else:
        print("店舗データが取得できませんでした。", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

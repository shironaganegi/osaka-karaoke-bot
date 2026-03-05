"""
Agent Watcher - ジャンカラ料金スクレイパー
==========================================
stations_master.json の各店舗から実際の料金データを取得する。

使い方:
    python agent_watcher/scrapers/jankara_pricing.py

出力先:
    data/stations_with_prices.json

料金ページの構造（2026年2月時点）:
    - .price_table.s_table  → 昼の料金テーブル
    - .price_table.n_table  → 夜の料金テーブル
    - td.price_time          → プラン名（30分、フリータイム等）
    - td.wd / td.hd          → 平日 / 土日祝
    - td.price span.fontPrice → 金額
    - カラム順: 学生会員, 学生, 会員, シニア, 一般
"""

import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout
except ImportError:
    print("エラー: playwright が必要です。 pip install playwright && playwright install", file=sys.stderr)
    sys.exit(1)


# ===================================================================
# 定数
# ===================================================================
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
INPUT_FILE = DATA_DIR / "stations_master.json"
OUTPUT_FILE = DATA_DIR / "stations_with_prices.json"

# リクエスト間隔（秒）- ボット検知回避
REQUEST_DELAY = 3

# ページ読み込みタイムアウト（ミリ秒）
PAGE_TIMEOUT = 15000

# 料金テーブルのセレクタ
SELECTORS = {
    "day_table": ".price_table.s_table",
    "night_table": ".price_table.n_table",
    "price_cell": "td.price",
    "font_price": "span.fontPrice",
    "time_cell": "td.price_time",
    "weekday_row": "td.wd",
}


def extract_price(text: str) -> int | None:
    """
    テキストから数値（料金）を抽出する。

    Args:
        text: 料金テキスト（例: "¥220", "220円", "220"）

    Returns:
        整数の料金、または None
    """
    if not text:
        return None
    # 数字のみ抽出（カンマ除去）
    cleaned = text.replace(",", "").replace("，", "")
    match = re.search(r"(\d+)", cleaned)
    return int(match.group(1)) if match else None


def scrape_table_prices(table_element) -> dict:
    """
    1つの料金テーブル（昼 or 夜）から料金を抽出する。

    テーブル構造:
        thead: カテゴリヘッダー（学生会員, 学生, 会員, シニア, 一般）
        tbody:
            各プラン（30分, フリータイム等）は rowspan=2 で平日/土日祝の2行
            td.price_time: プラン名 + 時間帯
            td.wd: 平日行のマーカー
            td.hd: 土日祝行のマーカー
            td.price > span.fontPrice: 金額

    Returns:
        dict: 抽出した料金データ
    """
    result = {}

    try:
        rows = table_element.query_selector_all("tbody tr")
        if not rows:
            return result

        current_plan = ""

        for row in rows:
            # プラン名の取得（rowspan行の場合のみ存在）
            time_cell = row.query_selector("td.price_time")
            if time_cell:
                current_plan = time_cell.inner_text().strip()
                # 改行で分割し、プラン名（30分, フリータイム等）を抽出
                plan_parts = current_plan.split("\n")
                current_plan = plan_parts[0].strip() if plan_parts else current_plan

            # 平日行かどうか判定
            is_weekday = row.query_selector("td.wd") is not None
            if not is_weekday:
                continue  # 土日祝行はスキップ（平日料金のみ取得）

            # 料金セルを取得
            price_cells = row.query_selector_all("td.price")
            if not price_cells:
                continue

            prices = []
            for cell in price_cells:
                font_el = cell.query_selector("span.fontPrice")
                if font_el:
                    price_val = extract_price(font_el.inner_text())
                    prices.append(price_val)
                else:
                    prices.append(None)

            # カラム順: 学生会員(0), 学生(1), 会員(2), シニア(3), 一般(4)
            member_price = prices[2] if len(prices) > 2 else None
            general_price = prices[4] if len(prices) > 4 else None

            # プラン名を正規化してキーにする
            plan_key = ""
            if "30分" in current_plan or "30min" in current_plan.lower():
                plan_key = "30min"
            elif "フリータイム" in current_plan or "フリー" in current_plan:
                plan_key = "free_time"
            else:
                # その他のプラン（60分等）は plan 名そのまま
                plan_key = current_plan.replace(" ", "_")

            if plan_key:
                result[plan_key] = {
                    "member": member_price,
                    "general": general_price,
                }

    except Exception as e:
        print(f"    テーブル解析エラー: {e}", file=sys.stderr)

    return result


def scrape_store_pricing(page, price_url: str) -> dict:
    """
    1店舗の料金ページから料金データを取得する。

    Args:
        page: Playwright のページオブジェクト
        price_url: 料金ページのURL

    Returns:
        dict: 料金データ
    """
    pricing = {
        "day": {},
        "night": {},
        "scraped_at": datetime.now().isoformat(),
        "status": "success",
    }

    try:
        page.goto(price_url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)

        # 料金テーブルが表示されるまで待機
        try:
            page.wait_for_selector(".price_table", timeout=8000)
        except PwTimeout:
            pricing["status"] = "no_table"
            return pricing

        # 昼の料金テーブル
        day_table = page.query_selector(SELECTORS["day_table"])
        if day_table:
            pricing["day"] = scrape_table_prices(day_table)

        # 夜の料金テーブル
        night_table = page.query_selector(SELECTORS["night_table"])
        if night_table:
            pricing["night"] = scrape_table_prices(night_table)

    except PwTimeout:
        pricing["status"] = "timeout"
    except Exception as e:
        pricing["status"] = f"error: {str(e)[:100]}"

    return pricing


def format_price_summary(pricing: dict) -> str:
    """
    料金データから表示用サマリーを生成する。

    Args:
        pricing: 料金データ辞書

    Returns:
        表示用文字列（例: "昼30分: 会員220円/一般325円"）
    """
    parts = []

    day_30 = pricing.get("day", {}).get("30min", {})
    if day_30.get("general"):
        member_str = f"会員{day_30['member']}円/" if day_30.get("member") else ""
        parts.append(f"昼30分: {member_str}一般{day_30['general']}円")

    day_ft = pricing.get("day", {}).get("free_time", {})
    if day_ft.get("general"):
        member_str = f"会員{day_ft['member']}円/" if day_ft.get("member") else ""
        parts.append(f"昼フリータイム: {member_str}一般{day_ft['general']}円")

    return " | ".join(parts) if parts else ""


    # 結果を駅グループに再構成（後で使うため、既存データ読み込み用関数を定義）
    
def load_existing_pricing() -> dict:
    """既存の出力ファイルから価格データを読み込む"""
    if not OUTPUT_FILE.exists():
        return {}
    try:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        cache = {}
        for station_stores in data.get("stations", {}).values():
            for store in station_stores:
                # unique key: price_url or url
                key = store.get("price_url") or store.get("url")
                if key and store.get("pricing"):
                    cache[key] = store["pricing"]
        return cache
    except Exception as e:
        print(f"キャッシュ読み込みエラー: {e}", file=sys.stderr)
        return {}


def main():
    """メイン実行関数"""
    print("=" * 60, file=sys.stderr)
    print("Agent Watcher - ジャンカラ料金スクレイピング", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    # 入力ファイル読み込み
    if not INPUT_FILE.exists():
        print(f"エラー: {INPUT_FILE} が見つかりません。", file=sys.stderr)
        sys.exit(1)

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        master_data = json.load(f)

    stations = master_data.get("stations", {})

    # 全店舗をフラットにリスト化
    all_stores = []
    for station, stores in stations.items():
        for store in stores:
            store["_station"] = station
            all_stores.append(store)

    total = len(all_stores)
    print(f"対象店舗数: {total}", file=sys.stderr)
    
    # キャッシュ読み込み
    pricing_cache = load_existing_pricing()
    print(f"キャッシュ済み店舗数: {len(pricing_cache)}", file=sys.stderr)

    print("-" * 60, file=sys.stderr)

    # スクレイピング実行
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            locale="ja-JP",
        )
        page = context.new_page()

        success_count = 0
        error_count = 0

        for i, store in enumerate(all_stores, 1):
            name = store.get("name", "不明")
            price_url = store.get("price_url") or store.get("url", "")
            
            # キャッシュチェック
            if price_url in pricing_cache:
                store["pricing"] = pricing_cache[price_url]
                # status check
                if store["pricing"].get("status") == "success":
                    print(f"  [{i}/{total}] {name}... (キャッシュ済み)", file=sys.stderr)
                    success_count += 1
                else:
                    # 失敗ステータスもキャッシュするならここ。
                    # 今回はスキップ済みの店舗(manekineko)もキャッシュされているはず
                     print(f"  [{i}/{total}] {name}... (キャッシュ: {store['pricing'].get('status')})", file=sys.stderr)
                     if store['pricing'].get('status') == 'skip':
                         pass
                     else:
                         error_count += 1
                continue


            if not price_url:
                store["pricing"] = {"status": "no_url"}
                error_count += 1
                continue

            # ジャンカラ以外はスキップ（今のところ）
            if store.get("chain") != "jankara":
                store["pricing"] = {"status": "skip"}
                print(f"  [{i}/{total}] {name}... (スキップ: {store.get('chain')})", file=sys.stderr)
                continue

            print(f"  [{i}/{total}] {name}...", end=" ", file=sys.stderr)

            pricing = scrape_store_pricing(page, price_url)
            store["pricing"] = pricing

            if pricing["status"] == "success":
                summary = format_price_summary(pricing)
                print(f"✅ {summary or '(データなし)'}", file=sys.stderr)
                success_count += 1
            else:
                print(f"⚠️ {pricing['status']}", file=sys.stderr)
                error_count += 1

            # レート制限
            if i < total:
                time.sleep(REQUEST_DELAY)

        browser.close()

    # 結果を駅グループに再構成
    result_stations = {}
    for store in all_stores:
        station = store.pop("_station")
        if station not in result_stations:
            result_stations[station] = []
        result_stations[station].append(store)

    # 出力データ構築
    output = {
        "generated_at": datetime.now().isoformat(),
        "total_stations": len(result_stations),
        "total_stores": total,
        "scraping_stats": {
            "success": success_count,
            "errors": error_count,
        },
        "stations": result_stations,
    }

    # 保存
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("=" * 60, file=sys.stderr)
    print(f"✅ 完了! 成功: {success_count}, エラー: {error_count}", file=sys.stderr)
    print(f"保存先: {OUTPUT_FILE}", file=sys.stderr)


if __name__ == "__main__":
    main()

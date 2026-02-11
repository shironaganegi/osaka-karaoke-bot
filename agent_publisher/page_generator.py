"""
Agent Publisher - Hugo ページ生成モジュール
==========================================
正規化済みデータから Hugo 用のマークダウンファイルを駅ごとに生成する。

- stations_with_prices.json がある場合は実際の料金を表示
- なければ stations_master.json から料金リンクのみのページを生成

使い方:
    python agent_publisher/page_generator.py

出力先:
    website/content/stations/{駅名}.md
"""

import json
import sys
from datetime import date
from pathlib import Path


def load_stations_data(data_dir: str = "data") -> dict | None:
    """
    データファイルを読み込む。
    stations_with_prices.json を優先、なければ stations_master.json。

    Returns:
        (JSONデータ, 料金データあり?)
    """
    data_path_prices = Path(data_dir) / "stations_with_prices.json"
    data_path_master = Path(data_dir) / "stations_master.json"

    if data_path_prices.exists():
        print(f"読み込み: {data_path_prices} (料金データ付き)", file=sys.stderr)
        with open(data_path_prices, "r", encoding="utf-8") as f:
            return json.load(f)

    if data_path_master.exists():
        print(f"読み込み: {data_path_master} (料金データなし)", file=sys.stderr)
        with open(data_path_master, "r", encoding="utf-8") as f:
            return json.load(f)

    print(
        "エラー: データファイルが見つかりません。\n"
        "先に agent_analyst/normalizer.py を実行してください。",
        file=sys.stderr,
    )
    return None


# =====================================================
# 定数
# =====================================================
CHAIN_ICONS = {
    "jankara": "🎤 ジャンカラ",
    "manekineko": "🐱 まねきねこ",
    "bigecho": "🎤 ビッグエコー",
}


def get_store_display_name(store: dict) -> str:
    """店舗の表示名（チェーンアイコン付き）を取得"""
    chain = store.get("chain", "jankara")
    icon = CHAIN_ICONS.get(chain, "🎤")
    name = store.get("name", "")
    return f"{icon} {name}"


def format_pricing_cell(store: dict) -> str:
    """
    店舗の料金情報をテーブルセル用に整形する。

    Args:
        store: 店舗データ（pricing キーを含む場合がある）

    Returns:
        表示用文字列
    """
    pricing = store.get("pricing")
    price_url = store.get("price_url") or store.get("url") or "#"

    if not pricing or pricing.get("status") != "success":
        # 料金データなし → 公式サイトへのリンク
        return f'[公式サイトで確認]({price_url})'

    parts = []

    # 昼30分料金
    day_30 = pricing.get("day", {}).get("30min", {})
    if day_30.get("general"):
        price_str = f"30分: {day_30['general']}円"
        if day_30.get("member"):
            price_str += f" (会員{day_30['member']}円)"
        parts.append(price_str)

    # 昼フリータイム
    day_ft = pricing.get("day", {}).get("free_time", {})
    if day_ft.get("general"):
        price_str = f"フリータイム: {day_ft['general']}円"
        if day_ft.get("member"):
            price_str += f" (会員{day_ft['member']}円)"
        parts.append(price_str)

    if parts:
        return " / ".join(parts)

    return f'[公式サイトで確認]({price_url})'


def build_store_table(stores: list[dict]) -> str:
    """
    店舗リストからマークダウンテーブルを組み立てる。
    """
    lines = []
    for store in stores:
        name_display = get_store_display_name(store)
        
        # 店舗名にリンクを貼る
        url = store.get("url") or store.get("price_url") or "#"
        name_col = f"[{name_display}]({url})"
        
        price_col = format_pricing_cell(store)
        
        # 公式料金表ボタン
        official_url = store.get("price_url") or store.get("url") or "#"
        official_col = f"[店舗ページ]({official_url})"

        lines.append(f"| {name_col} | {price_col} | {official_col} |")

    return "\n".join(lines)


def find_cheapest(stores: list[dict]) -> str:
    """
    最安値情報を生成する（料金データがある場合）。
    """
    cheapest_30 = None
    cheapest_30_name = ""
    cheapest_ft = None
    cheapest_ft_name = ""

    for s in stores:
        pricing = s.get("pricing", {})
        if pricing.get("status") != "success":
            continue

        day_30 = pricing.get("day", {}).get("30min", {})
        general_30 = day_30.get("general")
        if general_30 and (cheapest_30 is None or general_30 < cheapest_30):
            cheapest_30 = general_30
            cheapest_30_name = s.get("name", "")

        day_ft = pricing.get("day", {}).get("free_time", {})
        general_ft = day_ft.get("general")
        if general_ft and (cheapest_ft is None or general_ft < cheapest_ft):
            cheapest_ft = general_ft
            cheapest_ft_name = s.get("name", "")

    parts = []
    if cheapest_30:
        parts.append(f"- 🏆 **平日昼30分最安**: {cheapest_30}円（{cheapest_30_name}）")
    if cheapest_ft:
        parts.append(f"- 🏆 **平日昼フリータイム最安**: {cheapest_ft}円（{cheapest_ft_name}）")

    return "\n".join(parts) if parts else ""


def build_markdown(station: str, stores: list[dict], today: str) -> str:
    """
    駅ページのマークダウンコンテンツを生成する。
    """
    year = today[:4]
    store_count = len(stores)
    table_md = build_store_table(stores)
    cheapest_md = find_cheapest(stores)

    # エリア情報を取得（最初の店舗から）
    area = stores[0].get("area", "") if stores else ""

    # 最安値セクション
    cheapest_section = ""
    if cheapest_md:
        cheapest_section = f"""
### 💰 最安値ハイライト

{cheapest_md}

"""

    md = f"""---
title: "{station}のカラオケ最安値・店舗一覧【{year}年最新】"
description: "{station}駅周辺のジャンカラなどカラオケ店の料金比較。30分料金、フリータイム最安値を掲載。"
date: {today}
draft: false
keywords: ["{station} カラオケ", "{station} カラオケ 安い", "{station} ジャンカラ", "ジャンカラ"]
area: "{area}"
station: "{station}"
store_count: {store_count}
---

## {station}駅周辺のカラオケ店（{store_count}店舗）

{station}駅周辺にあるカラオケ店の料金・店舗情報をまとめました。各店舗の公式料金表へのリンクから、最新の料金プランを確認できます。
{cheapest_section}
| 店舗名 | 料金（平日昼） | 公式料金表 |
| --- | --- | --- |
{table_md}

> ※ 料金は時期・曜日・時間帯により異なります。最新情報は各店舗の公式サイトをご確認ください。

---

## {station}周辺でカラオケを探すコツ

- **平日昼間**が最も安い時間帯です
- **フリータイム**は長時間利用に最適
- **学生証**をお持ちの方は学割プランがお得です

---

<div class="affiliate-banner">
  <p>🎤 <strong>{station}周辺で遊んだあとの宿泊に</strong><br>
  <a href="https://travel.rakuten.co.jp/" rel="nofollow">楽天トラベルで{station}周辺のホテルを探す</a></p>
</div>

<div class="affiliate-banner">
  <p>🍽️ <strong>カラオケの前後にグルメも楽しむなら</strong><br>
  <a href="https://www.hotpepper.jp/" rel="nofollow">ホットペッパーで{station}周辺のお店を探す</a></p>
</div>
"""
    return md


def generate_pages(
    data_dir: str = "data",
    output_base: str = "website/content/stations",
) -> int:
    """全駅ページを生成する。"""
    raw = load_stations_data(data_dir)
    if raw is None:
        return 0

    stations = raw.get("stations", {})
    if not stations:
        print("エラー: stations データが空です。", file=sys.stderr)
        return 0

    output_dir = Path(output_base)
    output_dir.mkdir(parents=True, exist_ok=True)

    today = date.today().strftime("%Y-%m-%d")
    count = 0
    price_count = 0

    for station, stores in stations.items():
        if not station or station == "不明":
            print(f"  [スキップ] 駅名不明の店舗 ({len(stores)}件)", file=sys.stderr)
            continue

        # 料金データがある店舗数をカウント
        for s in stores:
            if s.get("pricing", {}).get("status") == "success":
                price_count += 1

        md_content = build_markdown(station, stores, today)

        filepath = output_dir / f"{station}.md"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(md_content)

        count += 1

    print(f"  料金データ付き店舗: {price_count}", file=sys.stderr)
    return count


def main():
    """メイン実行関数"""
    print("=" * 50, file=sys.stderr)
    print("Agent Publisher - Hugo ページ生成", file=sys.stderr)
    print("=" * 50, file=sys.stderr)

    count = generate_pages()

    if count > 0:
        print(f"\n✅ {count} ページを生成しました。", file=sys.stderr)
        print("出力先: website/content/stations/", file=sys.stderr)
    else:
        print("ページを生成できませんでした。", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

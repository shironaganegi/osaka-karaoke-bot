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
import urllib.parse
from datetime import date
from pathlib import Path


def load_stations_data(data_dir: str = "data") -> dict | None:
    """
    データファイルを読み込み、複数ソースの料金データをマージする。

    - stations_with_prices.json: ジャンカラの料金データ
    - stations_master.json: ビッグエコーの料金データ・URL

    両方のファイルから最新の料金データを統合して返す。
    """
    data_path_prices = Path(data_dir) / "stations_with_prices.json"
    data_path_master = Path(data_dir) / "stations_master.json"

    primary = None
    secondary = None

    # プライマリ: stations_with_prices.json（ジャンカラ料金）
    if data_path_prices.exists():
        print(f"読み込み: {data_path_prices} (料金データ付き)", file=sys.stderr)
        with open(data_path_prices, "r", encoding="utf-8") as f:
            primary = json.load(f)

    # セカンダリ: stations_master.json（ビッグエコー料金・URL等）
    if data_path_master.exists():
        print(f"読み込み: {data_path_master} (マスターデータ)", file=sys.stderr)
        with open(data_path_master, "r", encoding="utf-8") as f:
            secondary = json.load(f)

    if not primary and not secondary:
        print(
            "エラー: データファイルが見つかりません。\n"
            "先に agent_analyst/normalizer.py を実行してください。",
            file=sys.stderr,
        )
        return None

    if not primary:
        return secondary
    if not secondary:
        return primary

    # 両方あればマージ: secondary の料金データ・URL を primary に統合
    primary_stations = primary.get("stations", {})
    secondary_stations = secondary.get("stations", {})

    # secondary から店舗名→データの索引を作成
    sec_lookup: dict[str, dict] = {}
    for stores in secondary_stations.values():
        for s in stores:
            name = s.get("name", "")
            if name:
                sec_lookup[name] = s

    merged = 0
    for station, stores in primary_stations.items():
        for store in stores:
            name = store.get("name", "")
            sec_store = sec_lookup.get(name)
            if not sec_store:
                continue

            # 料金データをマージ（primary になければ secondary から）
            if not store.get("pricing") or store.get("pricing", {}).get("status") != "success":
                sec_pricing = sec_store.get("pricing", {})
                if sec_pricing.get("status") == "success":
                    store["pricing"] = sec_pricing
                    merged += 1

            # 座標データをマージ
            if not store.get("lat") and sec_store.get("lat"):
                store["lat"] = sec_store["lat"]
                store["lon"] = sec_store["lon"]

            # URL をマージ（primary が汎用URLの場合、secondary の具体URLに置換）
            pri_url = store.get("url", "")
            sec_url = sec_store.get("url", "")
            if sec_url and "shop_info" in sec_url and (
                not pri_url or "shop_search" in pri_url or pri_url == "#"
            ):
                store["url"] = sec_url

            # pdf_url をマージ
            if not store.get("pdf_url") and sec_store.get("pdf_url"):
                store["pdf_url"] = sec_store["pdf_url"]

    if merged > 0:
        print(f"  マージ: {merged} 店舗の料金データを統合", file=sys.stderr)

    return primary


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
    pdf_url = store.get("pdf_url")

    if not pricing or pricing.get("status") != "success":
        # 料金データなし
        if pdf_url:
            return f'[📄 料金表(PDF)]({pdf_url})'
        # なければ公式サイトへのリンク
        return f'[公式サイトで確認]({price_url})'

    parts = []

    # 昼30分料金
    day_30 = pricing.get("day", {}).get("30min", {})
    general_30 = day_30.get("general")
    member_30 = day_30.get("member")
    if general_30:
        price_str = f"30分: {general_30}円"
        if member_30:
            price_str += f" (会員{member_30}円)"
        parts.append(price_str)
    elif member_30:
        # general が null でも member があれば表示
        parts.append(f"30分: {member_30}円 (会員)")

    # 昼フリータイム
    day_ft = pricing.get("day", {}).get("free_time", {})
    general_ft = day_ft.get("general")
    member_ft = day_ft.get("member")
    if general_ft:
        price_str = f"フリータイム: {general_ft}円"
        if member_ft:
            price_str += f" (会員{member_ft}円)"
        parts.append(price_str)
    elif member_ft:
        parts.append(f"フリータイム: {member_ft}円 (会員)")

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
        
        # Google Maps リンク（座標がある場合）
        lat = store.get("lat")
        lon = store.get("lon")
        if lat and lon:
            gmap_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
            map_col = f"[📍 地図]({gmap_url})"
        else:
            # 住所で検索
            addr = store.get("address", "").split("\n")[0]
            if addr:
                gmap_url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(addr)}"
                map_col = f"[📍 地図]({gmap_url})"
            else:
                map_col = "-"

        lines.append(f"| {name_col} | {price_col} | {map_col} |")

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
        price_30 = day_30.get("general") or day_30.get("member")
        if price_30 and (cheapest_30 is None or price_30 < cheapest_30):
            cheapest_30 = price_30
            cheapest_30_name = s.get("name", "")

        day_ft = pricing.get("day", {}).get("free_time", {})
        price_ft = day_ft.get("general") or day_ft.get("member")
        if price_ft and (cheapest_ft is None or price_ft < cheapest_ft):
            cheapest_ft = price_ft
            cheapest_ft_name = s.get("name", "")

    parts = []
    if cheapest_30:
        parts.append(f"- 🏆 **平日昼30分最安**: {cheapest_30}円（{cheapest_30_name}）")
    if cheapest_ft:
        parts.append(f"- 🏆 **平日昼フリータイム最安**: {cheapest_ft}円（{cheapest_ft_name}）")

    return "\n".join(parts) if parts else ""


def build_map_section(stores: list[dict], station: str) -> str:
    """
    Leaflet.js マップの HTML/JS セクションを生成する。
    座標データがある店舗のみマーカーを表示。
    """
    # 座標がある店舗をフィルタ
    geo_stores = [
        s for s in stores
        if s.get("lat") and s.get("lon")
    ]

    if not geo_stores:
        return ""  # 座標データなし → マップ非表示

    # マップ中心座標（全店舗の平均）
    avg_lat = sum(s["lat"] for s in geo_stores) / len(geo_stores)
    avg_lon = sum(s["lon"] for s in geo_stores) / len(geo_stores)

    # チェーン別マーカーカラー
    chain_colors = {
        "jankara": "blue",
        "bigecho": "red",
        "manekineko": "gold",
    }

    # マーカーデータを生成
    markers_js = []
    for s in geo_stores:
        lat = s["lat"]
        lon = s["lon"]
        name = s.get("name", "").replace("'", "\\'")
        chain = s.get("chain", "jankara")
        color = chain_colors.get(chain, "blue")

        # 料金情報をポップアップに含める
        pricing = s.get("pricing", {})
        price_text = ""
        if pricing.get("status") == "success":
            day_30 = pricing.get("day", {}).get("30min", {})
            p = day_30.get("general") or day_30.get("member")
            if p:
                price_text = f"30分: {p}円"

        popup = f"{name}"
        if price_text:
            popup += f"<br>{price_text}"

        markers_js.append(
            f"      L.circleMarker([{lat}, {lon}], "
            f"{{radius: 10, color: '{color}', fillColor: '{color}', fillOpacity: 0.7}})"
            f".addTo(map).bindPopup('{popup}');"
        )

    markers_str = "\n".join(markers_js)

    return f"""
## 📍 {station}駅周辺カラオケマップ

<div id="map" style="height: 400px; width: 100%; border-radius: 8px; margin: 1em 0;"></div>

<p style="font-size: 0.85em; color: #888;">🔴 ビッグエコー　🔵 ジャンカラ　🟡 まねきねこ</p>

<script>
  (function() {{
    if (typeof L === 'undefined') return;
    var map = L.map('map').setView([{avg_lat}, {avg_lon}], 15);
    L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
      attribution: '&copy; <a href="https://openstreetmap.org">OpenStreetMap</a>',
      maxZoom: 19
    }}).addTo(map);
{markers_str}
  }})();
</script>
"""


def build_markdown(station: str, stores: list[dict], today: str) -> str:
    """
    駅ページのマークダウンコンテンツを生成する。
    """
    year = today[:4]
    store_count = len(stores)
    table_md = build_store_table(stores)
    cheapest_md = find_cheapest(stores)
    map_section = build_map_section(stores, station)

    # エリア情報を取得（最初の店舗から）
    area = stores[0].get("area", "") if stores else ""

    # 最安値セクション
    cheapest_section = ""
    if cheapest_md:
        cheapest_section = f"""
### 💰 最安値ハイライト

{cheapest_md}

"""

    # インライン広告（料金テーブルとマップの間）
    inline_ad_html = """
<style>
  .ad-epos-box {
    background-color: #fffbe6; /* Light yellow */
    border: 2px solid #f4d03f; /* Gold border */
    border-radius: 8px;
    padding: 15px;
    margin: 25px 0;
    text-align: center;
    color: #333;
  }
  .ad-epos-title {
    font-weight: bold;
    font-size: 1.1em;
    margin-bottom: 10px;
    color: #d35400;
  }
  .ad-epos-text {
    font-size: 0.9em;
    margin-bottom: 15px;
    text-align: left;
    line-height: 1.6;
  }
  .ad-epos-banner {
    margin-top: 10px;
    display: inline-block;
  }
</style>

<div class="ad-epos-box">
  <div class="ad-epos-title">💡 【裏技】カラオケ料金をさらに安くする方法</div>
  <div class="ad-epos-text">
    エポスカード（入会金・年会費永年無料）を持っているだけで、実はここから大幅割引になります。<br>
    🟥 <strong>ビッグエコー: 室料 30% OFF</strong><br>
    🟦 <strong>ジャンカラ: 室料 20% OFF</strong> (優待適用時)<br>
    <br>
    「今日作りたい」もOK（最短即日発行）。持っていないと正直損です。
  </div>
  
  <div class="ad-epos-banner">
    <script type='text/javascript' src='https://ad-verification.a8.net/ad/js/brandsafe.js'></script>
    <div id='div_admane_async_1734_658_2969'>
    <script type='text/javascript'>
    </script>
    </div>
    <img border="0" width="1" height="1" src="https://www12.a8.net/0.gif?a8mat=4AX9GH+CZDC76+38L8+BXIYP" alt="">
  </div>
</div>
"""

    # 固定フッター広告（Sticky Footer）
    sticky_footer_html = """
<div style="position: fixed; bottom: 0; left: 0; width: 100%; background: #333; color: #fff; padding: 10px; text-align: center; z-index: 9999; border-top: 3px solid #f4d03f; box-shadow: 0 -2px 10px rgba(0,0,0,0.3);">
  <span style="font-weight:bold; color: #f4d03f;">🉐 室料30%OFF!</span>
  <span style="font-size: 0.9em;">エポスカード持ってる？</span>
  <a href="https://px.a8.net/svt/ejp?a8mat=4AX9GH+CZDC76+38L8+BXIYP" target="_blank" rel="nofollow" style="background: #f4d03f; color: #000; padding: 5px 15px; border-radius: 4px; text-decoration: none; font-weight: bold; margin-left: 10px;">
    詳細を見る
  </a>
  <img border="0" width="1" height="1" src="https://www12.a8.net/0.gif?a8mat=4AX9GH+CZDC76+38L8+BXIYP" alt="">
</div>
<div style="height: 60px;"></div>
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
| 店舗名 | 料金（平日昼） | 地図 |
| --- | --- | --- |
{table_md}

> ※ 料金は時期・曜日・時間帯により異なります。最新情報は各店舗の公式サイトをご確認ください。

{inline_ad_html}

{map_section}
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

{sticky_footer_html}
"""
    return md


def save_stations_geo_json(stations: dict, output_path: str = "website/static/stations_geo.json"):
    """
    駅ごとの平均座標を計算し、フロントエンド用のJSONを生成する。
    """
    geo_data = []

    for station, stores in stations.items():
        if not station or station == "不明":
            continue

        lat_sum = 0
        lon_sum = 0
        count = 0

        for s in stores:
            if s.get("lat") and s.get("lon"):
                lat_sum += s["lat"]
                lon_sum += s["lon"]
                count += 1
        
        if count > 0:
            avg_lat = lat_sum / count
            avg_lon = lon_sum / count
            # URLエンコードされたパスが必要か確認 (Hugoは /stations/梅田/ のように生成される)
            geo_data.append({
                "name": station,
                "lat": round(avg_lat, 6),
                "lon": round(avg_lon, 6),
                "url": f"/stations/{station}/"
            })
    
    # staticディレクトリ作成
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(geo_data, f, ensure_ascii=False)
    
    print(f"  GeoJSON生成: {len(geo_data)} 駅の座標データ ({output_path})", file=sys.stderr)


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

    # フロントエンド用GeoJSON生成
    save_stations_geo_json(stations)

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

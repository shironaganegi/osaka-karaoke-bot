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



# =====================================================
# CSS スタイル (カードレイアウト & グリッド)
# =====================================================
STYLE_BLOCK = """
<style>
/* グリッドレイアウト (レスポンシブ) */
.store-list-container {
  display: grid;
  grid-template-columns: 1fr; /* スマホ: 1列 */
  gap: 20px;
  margin-bottom: 40px;
}

@media (min-width: 768px) {
  .store-list-container {
    grid-template-columns: repeat(2, 1fr); /* タブレット: 2列 */
  }
}

@media (min-width: 1024px) {
  .store-list-container {
    grid-template-columns: repeat(3, 1fr); /* PC: 3列 */
  }
}

/* カードスタイル */
.store-card {
  background: white;
  border-radius: 12px;
  box-shadow: 0 4px 6px rgba(0,0,0,0.05), 0 1px 3px rgba(0,0,0,0.1);
  padding: 20px;
  border: 1px solid #eee;
  display: flex;
  flex-direction: column;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.store-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 12px rgba(0,0,0,0.1);
}

/* 店舗名ヘッダー */
.store-header {
  margin-bottom: 15px;
  border-bottom: 1px solid #f0f0f0;
  padding-bottom: 10px;
}

.store-name {
  font-weight: bold;
  font-size: 1.1rem;
  color: #333;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.chain-badge {
  font-size: 0.8rem;
  padding: 2px 6px;
  border-radius: 4px;
  color: white;
  font-weight: normal;
}
.badge-jankara { background-color: #0044cc; } /* ジャンカラ青 */
.badge-bigecho { background-color: #cc0000; } /* ビッグエコー赤 */
.badge-manekineko { background-color: #f1c40f; color: #333; } /* まねきねこ黄 */

/* 料金グリッド */
.price-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-bottom: 20px;
  background: #f9f9f9;
  padding: 10px;
  border-radius: 8px;
}

.price-item {
  display: flex;
  flex-direction: column;
}

.price-label {
  font-size: 0.75rem;
  color: #888;
  margin-bottom: 2px;
}

.price-value {
  font-weight: bold;
  font-size: 0.95rem;
  color: #d35400; /* アクセントカラー */
}

/* アクションボタン */
.action-area {
  margin-top: auto; /* 下部に固定 */
  display: flex;
  gap: 10px;
}

.action-btn {
  flex: 1;
  text-align: center;
  padding: 8px 0;
  border-radius: 6px;
  font-size: 0.85rem;
  text-decoration: none;
  font-weight: bold;
  transition: background 0.2s;
  display: block; /* リンクを行全体に */
}

.btn-map {
  background-color: #f0f2f5;
  color: #555;
  border: 1px solid #dcdfe6;
}
.btn-map:hover { background-color: #e6e8eb; }

.btn-reserve {
  background-color: #3498db;
  color: white;
  border: 1px solid #2980b9;
}
.btn-reserve:hover { background-color: #2980b9; }

</style>
"""


def build_store_list_html(stores: list[dict]) -> str:
    """カード型リストHTMLを生成する (テーブル廃止・レスポンシブGrid)"""
    cards = []
    
    for store in stores:
        # 1. ヘッダー情報 (チェーン名削除ロジック)
        chain = store.get("chain", "jankara")
        raw_name = store.get("name", "")
        
        # 表示名の調整: "ジャンカラ ジャンカラ梅田店" -> "梅田店"
        display_name = raw_name
        chain_label = "その他"
        badge_class = "badge-jankara"

        if chain == "jankara":
            chain_label = "ジャンカラ"
            badge_class = "badge-jankara"
            display_name = display_name.replace("ジャンカラ", "").strip()
        elif chain == "bigecho":
            chain_label = "ビッグエコー"
            badge_class = "badge-bigecho"
            display_name = display_name.replace("ビッグエコー", "").strip()
        elif chain == "manekineko":
            chain_label = "まねきねこ"
            badge_class = "badge-manekineko"
            display_name = display_name.replace("カラオケまねきねこ", "").replace("まねきねこ", "").strip()

        # 2. 料金情報
        pricing = store.get("pricing")
        price_30_str = "-"
        price_ft_str = "-"
        
        if pricing and pricing.get("status") == "success":
            # 30分
            day_30 = pricing.get("day", {}).get("30min", {})
            p30 = day_30.get("general") or day_30.get("member")
            if p30:
                price_30_str = f"{p30}円〜"
            
            # フリータイム
            day_ft = pricing.get("day", {}).get("free_time", {})
            pft = day_ft.get("general") or day_ft.get("member")
            if pft:
                price_ft_str = f"{pft}円〜"
        
        # 3. リンク情報
        url = store.get("url") or store.get("price_url") or "#"
        
        # 地図リンク
        map_url = "#"
        lat = store.get("lat")
        lon = store.get("lon")
        if lat and lon:
            map_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
        else:
            addr = store.get("address", "").split("\n")[0]
            if addr:
                map_url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(addr)}"

        # カードHTML組み立て
        card = f"""
        <div class="store-card">
            <div class="store-header">
                <h3 class="store-name">
                    <span class="chain-badge {badge_class}">{chain_label}</span>
                    {display_name}
                </h3>
            </div>
            
            <div class="price-grid">
                <div class="price-item">
                    <span class="price-label">30分 (平日昼)</span>
                    <span class="price-value">{price_30_str}</span>
                </div>
                <div class="price-item">
                    <span class="price-label">フリータイム (平日昼)</span>
                    <span class="price-value">{price_ft_str}</span>
                </div>
            </div>

            <div class="action-area">
                <a href="{map_url}" target="_blank" rel="noopener" class="action-btn btn-map">📍 地図</a>
                <a href="{url}" target="_blank" rel="noopener" class="action-btn btn-reserve">🔗 予約・詳細</a>
            </div>
        </div>
        """
        cards.append(card)

    return f'<div class="store-list-container">{"".join(cards)}</div>'


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
    area = stores[0].get("area", "") if stores else ""
    
    # 1. 広告HTMLの定義 (関数内で確実に定義)
    
    # Inline Ad: 300x250 (ID 005)
    # コンテンツの合間に自然に配置できるレクタングルバナー
    inline_ad_html = """
<div style="margin: 30px 0; text-align: center;">
  <div style="font-size: 0.8rem; color: #999; margin-bottom: 5px;">PR</div>
  <div style="display: inline-block;">
    <script type='text/javascript' src='https://ad-verification.a8.net/ad/js/brandsafe.js'></script>
    <div id='div_admane_async_1734_658_2971'>
    <script type='text/javascript'>
    brandsafe_js_async('//ad-verification.a8.net/ad', '_site=1734&_article=658&_link=2971&_image=3218&_ns=1&sad=s00000015110002', '260212769785', '4AX9GH+CZDC76+38L8+BXQOH');
    </script>
    </div>
    <img border="0" width="1" height="1" src="https://www15.a8.net/0.gif?a8mat=4AX9GH+CZDC76+38L8+BXQOH" alt="">
  </div>
</div>
"""

    # Sticky Footer: 320x50 (ID 006)
    # シンプルな横並びレイアウト: テキスト + バナー
    sticky_footer_html = """
<div style="position: fixed; bottom: 0; left: 0; width: 100%; background: rgba(255, 255, 255, 0.95); border-top: 1px solid #ddd; z-index: 2147483647; display: flex; align-items: center; justify-content: center; padding: 4px 0; height: 58px; box-sizing: border-box;">
   <span style="font-size: 0.8rem; color: #333; margin-right: 10px; font-weight: bold; white-space: nowrap;">
     🉐 30%OFF <span style="font-size: 0.75rem;">エポスカード</span>
   </span>
   
   <div style="display: flex; align-items: center;">
    <script type='text/javascript' src='https://ad-verification.a8.net/ad/js/brandsafe.js'></script>
    <div id='div_admane_async_1734_658_2972'>
    <script type='text/javascript'>
    brandsafe_js_async('//ad-verification.a8.net/ad', '_site=1734&_article=658&_link=2972&_image=3219&_ns=1&sad=s00000015110002', '260212769785', '4AX9GH+CZDC76+38L8+BXYE9');
    </script>
    </div>
    <img border="0" width="1" height="1" src="https://www11.a8.net/0.gif?a8mat=4AX9GH+CZDC76+38L8+BXYE9" alt="">
   </div>
</div>
<div style="height: 60px;"></div>
"""

    # 2. コンテンツ生成
    # テーブルではなくカードリストを生成
    store_list_html = build_store_list_html(stores)
    cheapest_md = find_cheapest(stores)
    map_html = build_map_section(stores, station)

    # 最安値セクション
    cheapest_section = ""
    if cheapest_md:
        cheapest_section = f"### 💰 最安値ハイライト\n\n{cheapest_md}\n\n"

    # 3. コンテンツ組み立て (リスト結合で安全に)
    parts = []
    
    # ヘッダー & スタイル定義
    parts.append(f"""---
title: "{station}のカラオケ最安値・店舗一覧【{year}年最新】"
description: "{station}駅周辺のジャンカラなどカラオケ店の料金比較。30分料金、フリータイム最安値を掲載。"
date: {today}
draft: false
keywords: ["{station} カラオケ", "{station} カラオケ 安い", "{station} ジャンカラ", "ジャンカラ"]
area: "{area}"
station: "{station}"
store_count: {store_count}
---

{STYLE_BLOCK}

## {station}駅周辺のカラオケ店（{store_count}店舗）

{station}駅周辺にあるカラオケ店の料金・店舗情報をまとめました。各店舗の公式料金表へのリンクから、最新の料金プランを確認できます。
""")

    # 最安値 & 店舗リスト (カード型)
    parts.append(cheapest_section)
    parts.append(store_list_html)
    parts.append(f"""
> ※ 料金は時期・曜日・時間帯により異なります。最新情報は各店舗の公式サイトをご確認ください。
""")


    # インライン広告
    parts.append(inline_ad_html)

    # マップ
    parts.append(map_html)
    parts.append("\n---\n")

    # コツ & アフィリエイトバナー
    parts.append(f"""
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
""")

    # 固定フッター
    parts.append(sticky_footer_html)

    return "\n".join(parts)


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

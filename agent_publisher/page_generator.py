"""
Agent Publisher - Hugo ページ生成モジュール
==========================================
正規化済みデータから Hugo 用のマークダウンファイルを駅・エリアごとに生成する。

- stations_with_prices.json がある場合は実際の料金を表示
- なければ stations_master.json から料金リンクのみのページを生成

使い方:
    python agent_publisher/page_generator.py

出力先:
    website/content/stations/{駅名}.md
    website/content/areas/{エリア名}.md
"""

import json
import sys
import urllib.parse
from datetime import date
from pathlib import Path
from collections import defaultdict

# =====================================================
# 定数
# =====================================================
CHAIN_ICONS = {
    "jankara": "🎤 ジャンカラ",
    "manekineko": "🐱 まねきねこ",
    "bigecho": "🎤 ビッグエコー",
}

AREA_SLUGS = {
    "梅田": "umeda",
    "難波・心斎橋": "namba-shinsaibashi",
    "天王寺": "tennoji",
    "京橋": "kyobashi"
}


def load_stations_data(data_dir: str = "data") -> dict | None:
    """
    データファイルを読み込み、複数ソースの料金データをマージする。
    """
    data_path_prices = Path(data_dir) / "stations_with_prices.json"
    data_path_master = Path(data_dir) / "stations_master.json"

    primary = None
    secondary = None

    if data_path_prices.exists():
        print(f"読み込み: {data_path_prices} (料金データ付き)", file=sys.stderr)
        with open(data_path_prices, "r", encoding="utf-8") as f:
            primary = json.load(f)

    if data_path_master.exists():
        print(f"読み込み: {data_path_master} (マスターデータ)", file=sys.stderr)
        with open(data_path_master, "r", encoding="utf-8") as f:
            secondary = json.load(f)

    if not primary and not secondary:
        print("エラー: データファイルが見つかりません。", file=sys.stderr)
        return None

    if not primary: return secondary
    if not secondary: return primary

    primary_stations = primary.get("stations", {})
    secondary_stations = secondary.get("stations", {})

    sec_lookup = {}
    for stores in secondary_stations.values():
        for s in stores:
            name = s.get("name", "")
            if name: sec_lookup[name] = s

    for station, stores in primary_stations.items():
        for store in stores:
            name = store.get("name", "")
            sec_store = sec_lookup.get(name)
            if not sec_store: continue

            if not store.get("pricing") or store.get("pricing", {}).get("status") != "success":
                sec_pricing = sec_store.get("pricing", {})
                if sec_pricing.get("status") == "success":
                    store["pricing"] = sec_pricing

            if not store.get("lat") and sec_store.get("lat"):
                store["lat"] = sec_store["lat"]
                store["lon"] = sec_store["lon"]

            pri_url = store.get("url", "")
            sec_url = sec_store.get("url", "")
            if sec_url and "shop_info" in sec_url and (not pri_url or "shop_search" in pri_url or pri_url == "#"):
                store["url"] = sec_url

            if not store.get("pdf_url") and sec_store.get("pdf_url"):
                store["pdf_url"] = sec_store["pdf_url"]

    return primary


# =====================================================
# CSS スタイル (憲法第2条準拠: カードレイアウト & グリッド)
# =====================================================
STYLE_BLOCK = """
<style>
.store-list-container {
  display: grid;
  grid-template-columns: 1fr;
  gap: 15px;
  margin-bottom: 40px;
}
@media (min-width: 768px) {
  .store-list-container {
    grid-template-columns: repeat(2, 1fr);
  }
}
@media (min-width: 1024px) {
  .store-list-container {
    grid-template-columns: repeat(3, 1fr);
  }
}
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
.badge-jankara { background-color: #0044cc; }
.badge-bigecho { background-color: #cc0000; }
.badge-manekineko { background-color: #f1c40f; color: #333; }
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
  color: #d35400;
}
.action-area {
  margin-top: auto;
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
  display: block;
}
.btn-map {
  background-color: #f0f2f5;
  color: #555;
  border: 1px solid #dcdfe6;
}
.btn-reserve {
  background-color: #3498db;
  color: white;
  border: 1px solid #2980b9;
}
</style>
"""

# =====================================================
# 収益化パーツ (憲法第3条準拠: 一字一句変えない)
# =====================================================
INLINE_AD_HTML = """
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

STICKY_FOOTER_HTML = """
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


def build_store_list_html(stores: list[dict]) -> str:
    """カード型リストHTMLを生成する (憲法第3条: インデント禁止)"""
    cards = []
    
    for store in stores:
        chain = store.get("chain", "jankara")
        raw_name = store.get("name", "")
        
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

        pricing = store.get("pricing")
        price_30_str = "-"
        price_ft_str = "-"
        
        if pricing and pricing.get("status") == "success":
            day_30 = pricing.get("day", {}).get("30min", {})
            p30 = day_30.get("general") or day_30.get("member")
            if p30: price_30_str = f"{p30}円〜"
            
            day_ft = pricing.get("day", {}).get("free_time", {})
            pft = day_ft.get("general") or day_ft.get("member")
            if pft: price_ft_str = f"{pft}円〜"
        
        url = store.get("url") or store.get("price_url") or "#"
        map_url = "#"
        lat = store.get("lat")
        lon = store.get("lon")
        if lat and lon:
            map_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
        else:
            addr = store.get("address", "").split("\n")[0]
            if addr: map_url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(addr)}"

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
</div>"""
        cards.append(card)

    return f'<div class="store-list-container">{"".join(cards)}</div>'


def build_map_html(stores: list[dict]) -> str:
    """地図表示用のHTMLとスクリプトを生成する"""
    if not stores: return ""
    
    markers = []
    for s in stores:
        lat = s.get("lat")
        lon = s.get("lon")
        name = s.get("name", "")
        url = s.get("url") or "#"
        if lat and lon:
            markers.append({
                "name": name,
                "lat": lat,
                "lon": lon,
                "url": url
            })
    
    if not markers: return ""

    map_script = f"""
<div id="map" style="height: 400px; width: 100%; border-radius: 12px; margin-bottom: 40px; z-index: 1;"></div>
<script>
document.addEventListener('DOMContentLoaded', function() {{
    const markers = {json.dumps(markers, ensure_ascii=False)};
    if (markers.length === 0) return;

    // 中心座標を計算
    let latSum = 0;
    let lonSum = 0;
    markers.forEach(m => {{ latSum += m.lat; lonSum += m.lon; }});
    const center = [latSum / markers.length, lonSum / markers.length];

    const map = L.map('map').setView(center, 15);
    
    L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }}).addTo(map);

    markers.forEach(m => {{
        L.marker([m.lat, m.lon]).addTo(map)
            .bindPopup(`<a href="${{m.url}}" target="_blank"><b>${{m.name}}</b></a>`);
    }});
}});
</script>
"""
    return map_script


def find_cheapest(stores: list[dict]) -> str:
    """最安値情報を生成する"""
    cheapest_30 = None
    cheapest_30_name = ""
    cheapest_ft = None
    cheapest_ft_name = ""

    for s in stores:
        pricing = s.get("pricing", {})
        if pricing.get("status") != "success": continue

        day_30 = pricing.get("day", {}).get("30min", {})
        price_30 = day_30.get("general") or day_30.get("member")
        if price_30 is not None and (cheapest_30 is None or price_30 < cheapest_30):
            cheapest_30 = price_30
            cheapest_30_name = s.get("name", "")

        day_ft = pricing.get("day", {}).get("free_time", {})
        price_ft = day_ft.get("general") or day_ft.get("member")
        if price_ft is not None and (cheapest_ft is None or price_ft < cheapest_ft):
            cheapest_ft = price_ft
            cheapest_ft_name = s.get("name", "")

    parts = []
    if cheapest_30:
        parts.append(f"- 🏆 **平日昼30分最安**: {cheapest_30}円（{cheapest_30_name}）")
    if cheapest_ft:
        parts.append(f"- 🏆 **平日昼フリータイム最安**: {cheapest_ft}円（{cheapest_ft_name}）")

    return "\n".join(parts) if parts else ""


def build_markdown(station: str, stores: list[dict], today: str) -> str:
    """駅ページのマークダウンコンテンツを生成する"""
    year = today[:4]
    store_count = len(stores)
    area = stores[0].get("area", "") if stores else ""
    
    store_list_html = build_store_list_html(stores)
    map_html = build_map_html(stores)
    cheapest_md = find_cheapest(stores)

    cheapest_section = ""
    if cheapest_md:
        cheapest_section = f"### 💰 最安値ハイライト\n\n{cheapest_md}\n\n"

    area_link_section = ""
    if area in AREA_SLUGS:
        slug = AREA_SLUGS[area]
        area_link_section = f"\n\n---\n\n### 🔗 関連エリア情報\n- [{area}エリアのカラオケ店一覧・料金比較はこちら](/areas/{slug}/)\n"

    parts = [f"""---
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
""",
    cheapest_section,
    "\n\n" + store_list_html + "\n\n",
    "\n\n" + map_html + "\n\n",
    "\n> ※ 料金は時期・曜日・時間帯により異なります。最新情報は各店舗の公式サイトをご確認ください。\n",
    "\n\n" + INLINE_AD_HTML + "\n\n",
    area_link_section,
    "\n\n" + STICKY_FOOTER_HTML + "\n\n"
    ]

    return "".join(parts)


def build_area_markdown(area: str, stores: list[dict], today: str) -> str:
    """エリアまとめページのマークダウンコンテンツを生成する"""
    year = today[:4]
    store_count = len(stores)
    
    store_list_html = build_store_list_html(stores)
    cheapest_md = find_cheapest(stores)

    cheapest_section = ""
    if cheapest_md:
        cheapest_section = f"### 💰 エリア最安値ランキング\n\n{area}エリアで特に安い店舗はこちらです：\n\n{cheapest_md}\n\n"

    parts = [f"""---
title: "{area}エリアのカラオケ最安値・店舗比較まとめ【{year}年最新】"
description: "{area}エリア（主要駅周辺）のジャンカラ、ビッグエコー等の料金比較。30分料金、フリータイムが安い店を掲載。"
date: {today}
draft: false
keywords: ["{area} カラオケ", "{area} カラオケ 安い", "大阪 カラオケ 最安値"]
type: "area"
area: "{area}"
store_count: {store_count}
---

{STYLE_BLOCK}

## {area}エリアのカラオケ店一覧（{store_count}店舗）

{area}エリアにある各駅周辺のカラオケ店をまとめました。

""",
    cheapest_section,
    "\n\n" + store_list_html + "\n\n",
    "\n\n" + INLINE_AD_HTML + "\n\n",
    "\n\n" + STICKY_FOOTER_HTML + "\n\n"
    ]

    return "".join(parts)


def generate_area_pages(area_to_stores: dict, today: str, output_base: str = "website/content/areas"):
    """エリアごとのまとめページを生成する"""
    output_dir = Path(output_base)
    
    # 強制再生成: 既存のMarkdownファイルを削除
    if output_dir.exists():
        for file in output_dir.glob("*.md"):
            try:
                file.unlink()
            except Exception as e:
                print(f"Warning: Failed to delete {file}: {e}", file=sys.stderr)

    output_dir.mkdir(parents=True, exist_ok=True)
    count = 0

    for area, stores in area_to_stores.items():
        if area not in AREA_SLUGS: continue
        slug = AREA_SLUGS[area]
        md_content = build_area_markdown(area, stores, today)
        filepath = output_dir / f"{slug}.md"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(md_content)
        count += 1
    
    print(f"  エリアページ生成: {count} ページ", file=sys.stderr)


def generate_pages(data_dir: str = "data", output_base: str = "website/content/stations") -> int:
    """全ページを生成する"""
    raw = load_stations_data(data_dir)
    if raw is None: return 0

    stations = raw.get("stations", {})
    if not stations: return 0

    output_dir = Path(output_base)
    
    # 強制再生成: 既存のMarkdownファイルを削除
    if output_dir.exists():
        for file in output_dir.glob("*.md"):
            try:
                file.unlink()
            except Exception as e:
                print(f"Warning: Failed to delete {file}: {e}", file=sys.stderr)
    
    output_dir.mkdir(parents=True, exist_ok=True)

    today = date.today().strftime("%Y-%m-%d")
    count = 0
    area_to_stores = defaultdict(list)

    for station, stores in stations.items():
        if not station or station == "不明": continue
        
        # エリア集計用
        for s in stores:
            area = s.get("area")
            if area: area_to_stores[area].append(s)

        md_content = build_markdown(station, stores, today)
        filepath = output_dir / f"{station}.md"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(md_content)
        count += 1

    # エリアページ生成
    generate_area_pages(area_to_stores, today)
    
    return count


def main():
    print("=" * 50, file=sys.stderr)
    print("Agent Publisher - Hugo ページ生成 (エリア対応版)", file=sys.stderr)
    print("=" * 50, file=sys.stderr)

    count = generate_pages()

    if count > 0:
        print(f"\n✅ {count} 駅のページを生成しました。", file=sys.stderr)
    else:
        print("ページを生成できませんでした。", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

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
# CSS スタイル (外部ファイル custom.css に移動済み)
# =====================================================
# STYLE_BLOCK 削除済み

# =====================================================
# 収益化パーツ (憲法第3条準拠: 一字一句変えない -> クラス化のみ許可)
# =====================================================
INLINE_AD_HTML = """
<div class="ad-container">
  <div class="ad-pr-label">PR</div>
  <div class="ad-content">
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
<div class="sticky-footer">
   <span class="sticky-footer-badge">
     🉐 30%OFF <span class="sticky-footer-small">エポスカード</span>
   </span>
   
   <div class="sticky-footer-ad">
    <script type='text/javascript' src='https://ad-verification.a8.net/ad/js/brandsafe.js'></script>
    <div id='div_admane_async_1734_658_2972'>
    <script type='text/javascript'>
    brandsafe_js_async('//ad-verification.a8.net/ad', '_site=1734&_article=658&_link=2972&_image=3219&_ns=1&sad=s00000015110002', '260212769785', '4AX9GH+CZDC76+38L8+BXYE9');
    </script>
    </div>
    <img border="0" width="1" height="1" src="https://www11.a8.net/0.gif?a8mat=4AX9GH+CZDC76+38L8+BXYE9" alt="">
   </div>
</div>
<div class="sticky-footer-spacer"></div>
"""



def format_price(price_data: dict) -> str:
    """一般/会員価格を併記するフォーマット関数"""
    if not price_data:
        return "-"
        
    general = price_data.get("general")
    member = price_data.get("member")
    
    if general and member:
        return f"一般:{general}円<br>会員:{member}円"
    elif general:
        return f"{general}円"
    elif member:
        return f"<span class='member-label'>会員:</span>{member}円"
    else:
        return "-"

def get_lowest_price(price_data: dict) -> tuple[int | None, str]:
    """最安値とその種別（一般/会員）を返す"""
    if not price_data:
        return None, ""
        
    g = price_data.get("general")
    m = price_data.get("member")
    
    # 両方ある場合は安い方を返す（通常は会員）
    if g and m:
        if m < g: return m, "会員"
        return g, "一般"
    if m: return m, "会員"
    if g: return g, "一般"
    return None, ""


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
        data_price = "99999"
        
        if pricing and pricing.get("status") == "success":
            day_30 = pricing.get("day", {}).get("30min", {})
            price_30_str = format_price(day_30)
            
            day_ft = pricing.get("day", {}).get("free_time", {})
            price_ft_str = format_price(day_ft)

            # ソート用価格（最安値を使用）
            low_30, _ = get_lowest_price(day_30)
            if low_30:
                data_price = str(low_30)

            # デバッグログ: まねきねこの場合
            if chain == "manekineko":
                print(f"DEBUG: {display_name} - {price_30_str}", file=sys.stderr)
        
        url = store.get("url") or store.get("price_url") or "#"
        map_url = "#"
        lat = store.get("lat")
        lon = store.get("lon")
        if lat and lon:
            map_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
        else:
            addr = store.get("address", "").split("\n")[0]
            if addr: map_url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(addr)}"

        amenities = []
        if chain == "manekineko":
            amenities.append("mochikomi") # 持込OK
        if chain == "jankara":
            amenities.append("drinkbar") # ドリンクバー付(標準)
        
        data_amenities = " ".join(amenities)
        search_name = f"{chain_label} {display_name}"

        # PDFリンク作成
        pdf_link_html = ""
        pdf_url = store.get("pdf_url")
        if pdf_url:
            pdf_link_html = f'''<div class="pdf-link-container">
<a href="{pdf_url}" target="_blank" rel="noopener" class="pdf-link">📄 公式料金表を見る (PDF)</a>
</div>'''

        # カードHTML構築
        card = f"""
<div class="store-card" data-chain="{chain}" data-price="{data_price}" data-name="{search_name}" data-amenities="{data_amenities}">
<div class="store-header">
<h3 class="store-name">
<span class="chain-badge {badge_class}">{chain_label}</span>
{display_name}
</h3>
</div>
<div class="price-section">
<div class="price-item">
<span class="price-label">30分 (平日昼)</span>
<span class="price-value">{price_30_str}</span>
</div>
<div class="price-item">
<span class="price-label">フリータイム (平日昼)</span>
<span class="price-value">{price_ft_str}</span>
</div>
{pdf_link_html}
</div>
<div class="card-footer">
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
            # マーカーに価格情報も付与（最安値を表示）
            p_30 = "-"
            p_free = "-"
            pricing = s.get("pricing")
            if pricing and pricing.get("status") == "success":
                day_30 = pricing.get("day", {}).get("30min", {})
                low_30, type_30 = get_lowest_price(day_30)
                if low_30:
                    p_30 = f"{low_30}" 
                
                day_ft = pricing.get("day", {}).get("free_time", {})
                low_ft, type_ft = get_lowest_price(day_ft)
                if low_ft:
                    p_free = f"{low_ft}"

            markers.append({
                "name": name,
                "lat": lat,
                "lon": lon,
                "url": url,
                "price_30m": p_30,
                "price_free": p_free
            })
    
    if not markers: return ""

    # マーカーリストをJSON文字列に変換
    markers_json = json.dumps(markers, ensure_ascii=False)
    
    return f'{{{{< leaflet-map markers=`{markers_json}` >}}}}'


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
        price_30, type_30 = get_lowest_price(day_30)
        
        if price_30 is not None and (cheapest_30 is None or price_30 < cheapest_30):
            cheapest_30 = price_30
            # 種別が会員なら店舗名に付記
            suffix = f"（{type_30}）" if type_30 == "会員" else ""
            cheapest_30_name = f"{s.get('name', '')}{suffix}"

        day_ft = pricing.get("day", {}).get("free_time", {})
        price_ft, type_ft = get_lowest_price(day_ft)
        
        if price_ft is not None and (cheapest_ft is None or price_ft < cheapest_ft):
            cheapest_ft = price_ft
            suffix = f"（{type_ft}）" if type_ft == "会員" else ""
            cheapest_ft_name = f"{s.get('name', '')}{suffix}"

    parts = []
    if cheapest_30:
        parts.append(f"- 🏆 **平日昼30分最安**: {cheapest_30}円 / {cheapest_30_name}")
    if cheapest_ft:
        parts.append(f"- 🏆 **平日昼フリータイム最安**: {cheapest_ft}円 / {cheapest_ft_name}")

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

    # _index.md の生成（駅一覧用）
    index_md_path = output_dir / "_index.md"
    with open(index_md_path, "w", encoding="utf-8") as f:
        f.write('---\ntitle: "駅一覧"\n---\n')
    print(f"作成: {index_md_path}", file=sys.stderr)

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

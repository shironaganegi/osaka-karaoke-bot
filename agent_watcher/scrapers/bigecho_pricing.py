import json
import re
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

def load_master_data():
    path = Path("data/stations_master.json")
    if not path.exists():
        print("Error: stations_master.json not found.")
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_master_data(data):
    path = Path("data/stations_master.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def extract_price(text):
    """
    文字列から数値を抽出する (例: "350円" -> 350)
    "〜"が含まれる場合は下限を採用する
    """
    if not text:
        return None
    
    # 全角数字を半角に
    text = text.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    # カンマ削除
    text = text.replace(",", "")
    
    # "350円〜" などの場合、最初の数値を抽出
    match = re.search(r'(\d+)', text)
    if match:
        return int(match.group(1))
    return None

import sys
# WindowsでUTF-8出力を強制
sys.stdout.reconfigure(encoding='utf-8')

def get_store_url_from_shop_search(page, store_name):
    """
    店舗検索サイト(shop.big-echo.jp)を使って確実なURLを取得する
    """
    print(f"  Searching shop app for: {store_name}")
    try:
        page.goto("https://shop.big-echo.jp/", timeout=30000)
        
        # 検索ボックス待機
        search_input = page.locator('input[placeholder*="地名"], input[placeholder*="駅名"], input#keyword').first
        try:
            search_input.wait_for(state="visible", timeout=15000)
        except:
            return None
        
        # 検索クエリのバリエーション
        queries = []
        name_only = store_name.replace("カラオケ", "").replace("ビッグエコー", "").strip()
        if name_only: queries.append(name_only)
        
        # 駅名っぽいのを抜く (なんば戎橋店 -> 戎橋店, なんばアムザ店 -> アムザ店)
        parts = name_only.split()
        if len(parts) > 1: queries.append(parts[-1])
        
        # それでもダメならそのまま
        if store_name not in queries: queries.append(store_name)

        final_url = None
        for q in queries:
            if not q: continue
            print(f"    Trying query: {q}")
            search_input.fill(q)
            search_input.press("Enter")
            page.wait_for_timeout(3000) 
            
            # 検索結果をチェック
            items = page.locator('.result-box ul.stores li:not(.result-heading)').all()
            target_item = None
            for item in items:
                item_name = item.locator('.name').text_content() or ""
                # 相互に部分一致するか
                c_item = item_name.replace(" ", "").replace("　", "").replace("店", "")
                c_query = name_only.replace(" ", "").replace("　", "").replace("店", "")
                if c_query in c_item or c_item in c_query:
                    target_item = item
                    break
            
            if target_item:
                target_item.click()
                page.wait_for_timeout(1000) 
                
                detail_link = page.locator('a:has-text("店舗詳細"), a.btn-detail').last
                if detail_link.is_visible():
                    pages_count = len(page.context.pages)
                    detail_link.click()
                    page.wait_for_timeout(5000) 
                    
                    if len(page.context.pages) > pages_count:
                        new_page = page.context.pages[-1]
                        new_page.wait_for_load_state()
                        final_url = new_page.url
                        new_page.close()
                    else:
                        final_url = page.url
                    
                    if final_url and ("big-echo.jp" in final_url and "shop.big-echo.jp" not in final_url):
                        return final_url
            
            # 次のクエリを試す前に再検索ページへ
            if not final_url:
                page.goto("https://shop.big-echo.jp/", timeout=20000)
                search_input = page.locator('input#keyword').first
                search_input.wait_for(state="visible", timeout=10000)

    except Exception as e:
        print(f"    Map search failed: {e}")
            
    return None

def parse_bigecho_table(table_locator):
    """
    ビッグエコーの料金テーブルから平日・会員/一般価格を抽出する
    """
    result = {"member": None, "general": None}
    
    try:
        rows = table_locator.locator("tr").all()
        if not rows:
            return result

        weekday_col_idx = -1
        for row in rows:
            headers = row.locator("th, td").all()
            if len(headers) < 2: continue
            
            for i, h in enumerate(headers):
                txt = h.text_content() or ""
                if "平日" in txt or "月〜金" in txt:
                    weekday_col_idx = i
                    break
            if weekday_col_idx != -1:
                break
        
        if weekday_col_idx == -1:
            for row in rows:
                headers = row.locator("th, td").all()
                if len(headers) >= 2:
                    weekday_col_idx = 1
                    break
            if weekday_col_idx == -1: weekday_col_idx = 0
            
        print(f"    Table Weekday index: {weekday_col_idx}")

        # 1次解析: 行の役割を特定
        for row in rows:
            text = (row.text_content() or "").strip()
            cols = row.locator("td, th").all()
            if len(cols) <= weekday_col_idx: continue
                
            raw_target = cols[weekday_col_idx].text_content()
            price = extract_price(raw_target)
            if not price: continue
            
            # 会員: "会員"が含まれ、且つ"以外"が含まれない
            if "会員" in text and "以外" not in text:
                result["member"] = price
            # 一般: "一般" または "会員以外"
            elif "一般" in text or "会員以外" in text or "以外" in text:
                result["general"] = price
            # 学生/シニアなどは、会員・一般の両方が見つからない場合のフォールバックとしてのみ使用
            elif not result["member"] and ("学割" in text or "学生" in text or "シニア" in text):
                # 暫定的にmemberに入れるが、後で"会員"行が見つかれば上書きされる
                result["member"] = price

    except Exception as e:
        print(f"    Table parse error: {e}")
        
    return result

def scrape_store_pricing(page, url):
    print(f"Scraping: {url}")
    try:
        page.goto(url, timeout=30000)
        page.wait_for_load_state("domcontentloaded")
        
        # 料金表タブをクリック (セレクタを強化)
        price_tab = page.locator('a[title="料金表"], .shop_tab_item:has-text("料金表"), li:has-text("料金表"), a:has-text("料金表")').first
        if price_tab.count() > 0 and price_tab.is_visible():
            price_tab.click()
            page.wait_for_timeout(2000)
        
        pricing_data = {
            "day": {
                "30min": {"member": None, "general": None},
                "free_time": {"member": None, "general": None}
            }
        }

        # すべての料金ヘッダーを取得 (h4.ttype1 が公式アコーディオン)
        headers = page.locator('h4.ttype1, .shop_price_item h4, h4:has-text("OPEN"), h4:has-text("フリータイム")').all()
        
        for header in headers:
            txt = (header.text_content() or "").replace("\n", "").replace("\t", "").strip()
            if not header.is_visible(): continue
            
            # 1. 昼30分 (OPEN〜且つフリータイムを含まない)
            if "OPEN" in txt and "フリータイム" not in txt and not pricing_data["day"]["30min"]["member"]:
                print(f"  Target 30min header: {txt[:40]}")
                header.click()
                page.wait_for_timeout(1000)
                
                table = header.locator('xpath=following::table[1]').first
                if table.count() > 0:
                    pricing_data["day"]["30min"] = parse_bigecho_table(table)
                    print(f"    30min Data: {pricing_data['day']['30min']}")
            
            # 2. 昼フリータイム
            elif ("昼フリータイム" in txt or ("フリータイム" in txt and "昼" in txt)) and not pricing_data["day"]["free_time"]["member"]:
                print(f"  Target FreeTime header: {txt[:40]}")
                header.click()
                page.wait_for_timeout(1000)
                
                table = header.locator('xpath=following::table[1]').first
                if table.count() > 0:
                    pricing_data["day"]["free_time"] = parse_bigecho_table(table)
                    print(f"    FreeTime Data: {pricing_data['day']['free_time']}")

        if pricing_data["day"]["30min"]["member"] or pricing_data["day"]["free_time"]["member"]:
            return pricing_data
        
        return None

    except Exception as e:
        print(f"  Error scraping {url}: {e}")
        return None

def main():
    data = load_master_data()
    
    all_stores = []
    stations = data.get("stations", {})
    for station_name, store_list in stations.items():
        for store in store_list:
            if store.get("chain") == "bigecho" or store.get("name", "").startswith("ビッグエコー") or store.get("name", "").startswith("カラオケ ビッグエコー"):
                # 重複回避のため、名前と駅の組み合わせで一意にする
                store["_station_key"] = station_name
                all_stores.append(store)
        
    print(f"Found {len(all_stores)} Big Echo store entries.")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()
        
        updated_count = 0
        
        # 処理済みの店舗URLを記録して重複アクセスを避ける
        processed_urls = {}
        
        for store in all_stores:
            name = store.get("name")
            url = store.get("url")
            
            # 取得済みデータがある場合は再利用（キャッシュ）
            cache_key = f"{name}"
            if cache_key in processed_urls:
                store["url"] = processed_urls[cache_key].get("url")
                store["pricing"] = processed_urls[cache_key].get("pricing")
                continue

            # 既存のpricingデータが成功しているならスキップ
            if store.get("pricing") and store.get("pricing").get("status") == "success":
                processed_urls[cache_key] = {"url": url, "pricing": store["pricing"]}
                continue
            
            should_search = False
            if not url or "big-echo.jp" not in url:
                should_search = True
            elif "big-echo.jp/shop_info/" in url and "?p=" not in url:
                should_search = True
            elif "shop.big-echo.jp" in url:
                should_search = True

            if should_search:
                new_url = get_store_url_from_shop_search(page, name)
                if new_url:
                    print(f"  URL Updated: {new_url}")
                    store["url"] = new_url
                    url = new_url
                    save_master_data(data)
                else:
                     print(f"  Skipping {name} (URL not found)")
                     continue
            
            pricing = scrape_store_pricing(page, url)
            
            if pricing:
                pricing["status"] = "success"
                store["pricing"] = pricing
                updated_count += 1
                processed_urls[cache_key] = {"url": url, "pricing": pricing}
                save_master_data(data)
            else:
                store["pricing"] = {"status": "error"}
            
            time.sleep(2)
            
        browser.close()
        
    print(f"Updated pricing for {updated_count} stores.")
    save_master_data(data)


if __name__ == "__main__":
    main()

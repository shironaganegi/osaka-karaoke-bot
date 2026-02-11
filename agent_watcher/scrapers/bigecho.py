import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright

BASE_URL = "https://big-echo.jp/shop_search/area/osaka/"
OUTPUT_DIR = Path("data")
OUTPUT_DIR.mkdir(exist_ok=True)

async def scrape_bigecho_osaka():
    # Windowsコンソールでの文字化け防止
    sys.stdout.reconfigure(encoding='utf-8')
    print(f"[{datetime.now().strftime('%H:%M:%S')}] ビッグエコー(大阪)のスクレイピング開始...")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # 画面サイズを大きめにして要素が隠れないようにする
        page = await browser.new_page(viewport={"width": 1280, "height": 800})
        
        # UserAgentを設定
        await page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })

        stores = []

        try:
            # 1. 店舗検索トップへ
            top_url = "https://big-echo.jp/shop_search/"
            print(f"店舗検索ページへアクセス: {top_url}")
            await page.goto(top_url, timeout=60000)
            
            # ランディングページ（都道府県選択）の処理
            print("ランディングページを確認中...")

            # 「大阪府」のリンクを探す
            # 属性あてで探す
            osaka_link = page.locator('a[title="大阪府"]').first
            if await osaka_link.count() == 0:
                osaka_link = page.locator('a', has_text="大阪府").first
            
            if await osaka_link.count() > 0:
                print("大阪府のリンクを発見、クリックします。")
                await osaka_link.click()
            else:
                print("大阪府のリンクが見つかりません。直接マップアプリURLへ遷移を試みます。")
                await page.goto("https://shop.big-echo.jp/")

            # マップアプリ画面での操作
            print("地図アプリ画面でのロード待機中...")
            
            # 検索ボックスが表示されるまで待つ
            try:
                await page.wait_for_selector(".sl-search-box", timeout=20000)
            except:
                print("検索ボックスの表示タイムアウト。")
                
            # 検索ボックスに「大阪」と入力して、オートコンプリートを待つ
            search_input = page.locator('input[placeholder="地名・駅名などを入力"]').first
            if await search_input.count() > 0:
                print("検索ボックスに「大阪」を入力...")
                await search_input.fill("大阪")
                await page.wait_for_timeout(1500) # オートコンプリート表示待ち
                
                # オートコンプリート (.pac-item) を探してクリック
                pac_item = page.locator(".pac-item").first
                if await pac_item.count() > 0:
                    print("オートコンプリート候補をクリックします。")
                    await pac_item.click()
                else:
                    print("オートコンプリートが出ないため、Enterキーを押します。")
                    await search_input.press("Enter")
            
            await page.wait_for_timeout(3000)

            # 店舗リスト (.result-box ul.stores li) の出現待機
            # 出ない場合はマップ上のエリアラベルをクリック
            try:
                await page.wait_for_selector(".result-box ul.stores li:not(.result-heading)", timeout=5000)
                print("店舗リストが表示されました。")
            except:
                print("店舗リストが自動表示されませんでした。マップ上のラベルをクリックしてみます。")
                # 大阪市などを探してクリック
                area_label = page.locator(".sl-area-label", has_text="大阪市").first
                if await area_label.count() > 0:
                    print("エリアラベル(大阪市)をクリック...")
                    await area_label.click()
                    await page.wait_for_timeout(3000)
                else:
                    # 任意のラベルをクリック
                    any_label = page.locator(".sl-area-label").first
                    if await any_label.count() > 0:
                        print("任意のエリアラベルをクリック...")
                        await any_label.click()
                        await page.wait_for_timeout(3000)

            # 再度リスト確認
            cards = page.locator(".result-box ul.stores li:not(.result-heading)")
            count = await cards.count()
            print(f"現在のリスト表示数: {count} 件")

            if count == 0:
                print("店舗リストを取得できませんでした。デバッグHTMLを保存します。")
                html_content = await page.content()
                with open("debug_bigecho_app_v2.html", "w", encoding="utf-8") as f:
                    f.write(html_content)
                return []

            # 無限スクロール（サイドバー内）
            sidebar = page.locator('.sidebar .scroll-area')
            # DOM構造によっては .result-box がスクロール対象かも
            # debug_bigecho_app.html によると .scroll-area { overflow: auto; }
            
            if await sidebar.count() > 0:
                print("全件読み込みのためスクロールします...")
                last_count = 0
                retries = 0
                while retries < 3:
                    # JSでスクロール最下部へ
                    await page.evaluate("(el) => el.scrollTop = el.scrollHeight", await sidebar.element_handle())
                    await page.wait_for_timeout(1500)
                    
                    new_count = await cards.count()
                    if new_count == last_count:
                        retries += 1
                    else:
                        retries = 0
                        last_count = new_count
                        print(f"読み込み中... 現在 {new_count} 件")
            
            # データ抽出
            print("データを抽出します...")
            unique_stores = {}
            
            # 再取得（スクロール後）
            cards = page.locator(".result-box ul.stores li:not(.result-heading)")
            count = await cards.count()
            
            for i in range(count):
                li = cards.nth(i)
                try:
                    name_el = li.locator(".name")
                    addr_el = li.locator(".address")
                    
                    if await name_el.count() == 0: continue
                    
                    name = await name_el.inner_text()
                    address = await addr_el.inner_text() if await addr_el.count() > 0 else ""
                    
                    # 店舗除外（大阪以外が混ざる可能性）
                    if "大阪" not in address:
                        continue

                    # URL生成 (詳細ページへの直接リンクがないので、検索ページURLとするか、後で考える)
                    # ビッグエコー公式サイトの店舗URLパターンは https://big-echo.jp/shop_search/shop/[shop_id]/
                    # しかしIDがここにあるか不明。今のところトップURLにしておく。
                    url = "https://big-echo.jp/shop_search/"

                    store_data = {
                        "name": name.strip(),
                        "chain": "bigecho",
                        "address": address.strip().replace("\n", ""),
                        "url": url
                    }
                    
                    unique_stores[name.strip()] = store_data
                    
                except Exception as e:
                    print(f"要素解析エラー({i}): {e}")

            stores = list(unique_stores.values())
            print(f"有効な店舗データ: {len(stores)} 件")

            # 保存
            timestamp = datetime.now().strftime("%Y%m%d")
            filename = OUTPUT_DIR / f"raw_bigecho_{timestamp}.json"
            
            with open(filename, "w", encoding="utf-8") as f:
                json.dump({"date": timestamp, "stores": stores}, f, indent=2, ensure_ascii=False)
            
            print(f"保存完了: {filename}")

        except Exception as e:
            print(f"重大なエラー: {e}")
            import traceback
            traceback.print_exc()
            # エラー時HTML保存
            try:
                html_content = await page.content()
                with open("debug_bigecho_error_v2.html", "w", encoding="utf-8") as f:
                    f.write(html_content)
            except:
                pass
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape_bigecho_osaka())

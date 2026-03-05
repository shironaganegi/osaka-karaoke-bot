from playwright.sync_api import sync_playwright

def research_karaokekan_playwright():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            print("Navigating to https://karaokekan.jp/shop/osaka ...")
            page.goto("https://karaokekan.jp/shop/osaka", timeout=30000)
            
            # 店舗リストが表示されるまで少し待つ
            page.wait_for_selector("a[href*='/shop/osaka/']", timeout=5000)
            
            # リンクを取得
            links = page.query_selector_all("a[href*='/shop/osaka/']")
            print(f"Found {len(links)} store links.")
            
            unique_stores = set()
            for link in links:
                href = link.get_attribute("href")
                if href:
                    unique_stores.add(href)
            
            print(f"Unique store URLs: {len(unique_stores)}")
            for url in list(unique_stores)[:5]:
                print(f"- {url}")
                
        except Exception as e:
            print(f"Error: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    research_karaokekan_playwright()

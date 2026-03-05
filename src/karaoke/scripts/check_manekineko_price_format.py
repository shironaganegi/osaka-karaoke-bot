import json
from playwright.sync_api import sync_playwright
import time

def check_price_format():
    with open('data/stations_master.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    manekineko_stores = []
    # dataは辞書全体なので、'stations'キーの値を使用する
    stations_data = data.get('stations', {})
    for station in stations_data.values():
        for store in station:
            if store['chain'] == 'manekineko':
                manekineko_stores.append(store)

    print(f"Total Manekineko stores: {len(manekineko_stores)}")
    
    # Check first 5 stores
    targets = manekineko_stores[:5]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )

        for store in targets:
            page = context.new_page()
            url = store['url']
            store_name = store.get('name', 'Unknown Store')
            print(f"Checking {store_name} ({url})...")
            
            try:
                page.goto(url, timeout=30000)
                page.wait_for_load_state("domcontentloaded")
                
                # Check for table in #price
                price_section = page.locator("#price")
                if price_section.count() > 0:
                    has_table = price_section.locator("table").count() > 0
                    has_pdf_link = price_section.locator("a[href$='.pdf']").count() > 0
                    
                    print(f"  Result for {store_name}:")
                    print(f"    Has Table: {has_table}")
                    print(f"    Has PDF Link: {has_pdf_link}")
                    
                    # Dump content if interesting
                    if has_table:
                        print("    Found TABLE! Dumping content...")
                        print(price_section.inner_html())
                    elif has_pdf_link:
                        print("    Found PDF Link.")
                        # PDFリンクのURLを表示
                        pdf_link_el = price_section.locator("a[href$='.pdf']").first
                        print(f"    PDF URL: {pdf_link_el.get_attribute('href')}")
                    else:
                        print("    Neither Table nor PDF link found immediately. Dumping HTML...")
                        print(price_section.inner_html())

                else:
                    print("  Price section (#price) not found.")

            except Exception as e:
                print(f"  Error checking {store_name}: {e}")
            
            page.close()

        browser.close()

if __name__ == "__main__":
    check_price_format()

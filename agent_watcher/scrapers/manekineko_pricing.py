import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

def load_master_data():
    path = Path("data/stations_master.json")
    if not path.exists():
        print("Error: data/stations_master.json not found.")
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_master_data(data):
    path = Path("data/stations_master.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Updated {path}")

def scrape_manekineko_pdf_links():
    data = load_master_data()
    if not data:
        return

    # Extract Manekineko stores safely
    manekineko_stores = []
    # data can be list or dict depending on previous steps, but structure suggests:
    # { ..., "stations": { "station_name": [ {store}, ... ] } }
    
    stations_data = data.get("stations", {})
    
    # Create a flat list of (station_name, store_index, store_data) tuples to update later
    targets = []
    
    for station_name, stores in stations_data.items():
        for idx, store in enumerate(stores):
            if store.get("chain") == "manekineko":
                targets.append({
                    "station_name": station_name,
                    "index": idx,
                    "store": store
                })

    print(f"Found {len(targets)} Manekineko stores to check.")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
        
        # Batch processing not needed for 30 stores, but good practice
        for i, target in enumerate(targets):
            store = target["store"]
            url = store.get("url")
            store_name = store.get("name", "Unknown")
            
            print(f"[{i+1}/{len(targets)}] Checking {store_name}...")
            
            if not url:
                print("  Skipping: No URL")
                continue

            page = context.new_page()
            try:
                page.goto(url, timeout=30000)
                # Ensure price section is loaded or at least DOM is ready
                page.wait_for_load_state("domcontentloaded")
                
                # Try to find PDF link in #price section
                # Typically: <dl id="price"> ... <a href="...pdf"> ... </dl>
                pdf_link_locator = page.locator("#price a[href$='.pdf']").first
                
                pdf_url = None
                if pdf_link_locator.count() > 0:
                    pdf_url = pdf_link_locator.get_attribute("href")
                    print(f"  Found PDF: {pdf_url}")
                else:
                    print("  No PDF link found in #price section.")
                    # Fallback: check whole page for price pdf? Might be risky.
            
            except Exception as e:
                print(f"  Error scraping {store_name}: {e}")
                pdf_url = None
            finally:
                page.close()
            
            # Update data in memory
            if pdf_url:
                # Update the specific store in the main data structure
                data["stations"][target["station_name"]][target["index"]]["pdf_url"] = pdf_url
                # Optional: Update price_url to point to PDF if prefered
                # data["stations"][target["station_name"]][target["index"]]["price_url"] = pdf_url

            # Be polite
            time.sleep(1)

        browser.close()

    # Save updated data
    save_master_data(data)

if __name__ == "__main__":
    scrape_manekineko_pdf_links()

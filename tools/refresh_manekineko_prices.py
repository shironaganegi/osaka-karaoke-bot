
import sys
import os
import json
import time
import logging
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from agent_scraper.manekineko_pdf import fetch_pdf_url, download_pdf, extract_prices_from_pdf

# Setup simple logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TARGET_STORES = [
    "カラオケまねきねこ 梅田芝田店",
    "カラオケまねきねこ 茶屋町店",
    "カラオケまねきねこ 阪急東通り店",
    "カラオケまねきねこ 阪急東通り2号店"
]

def extract_prices_for_store(store_name, store_url):
    """
    Orchestrates the scraping flow for a single store.
    """
    logger.info(f"Scraping {store_name} from {store_url}...")
    
    pdf_url = fetch_pdf_url(store_url)
    if not pdf_url:
        logger.warning(f"  PDF not found for {store_name}")
        return None
        
    logger.info(f"  PDF URL: {pdf_url}")
    
    pdf_bytes = download_pdf(pdf_url)
    if not pdf_bytes:
        logger.warning(f"  Failed to download PDF for {store_name}")
        return None
        
    prices = extract_prices_from_pdf(pdf_bytes)
    return prices

def main():
    json_path = project_root / "data/stations_with_prices.json"
    
    if not json_path.exists():
        logger.error(f"{json_path} not found.")
        return

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    logger.info("🔥 Starting forced price refresh for Manekineko...")
    updated_count = 0

    # Traverse all stations and stores
    if "stations" in data:
        # Check if stations is dict or list (based on previous findings it's a dict)
        if isinstance(data["stations"], dict):
            iterator = data["stations"].items()
        else:
            logger.error("Unexpected JSON structure: 'stations' is not a dict.")
            return

        for station_name, stores in iterator:
            for store in stores:
                # Fuzzy match or exact match
                if any(target in store.get("name", "") for target in TARGET_STORES):
                    logger.info(f"Target found: {store['name']}")
                    
                    # Force scrape
                    try:
                        old_price = store.get("pricing", {}).get("day", {}).get("30min", {}).get("member")
                        
                        if store.get("url"):
                            new_pricing = extract_prices_for_store(store["name"], store["url"])
                            
                            if new_pricing and new_pricing.get("status") == "success":
                                # Update pricing
                                store["pricing"] = new_pricing
                                new_price = new_pricing.get("day", {}).get("30min", {}).get("member")
                                logger.info(f"✅ Updated {store['name']}: {old_price} -> {new_price}")
                                updated_count += 1
                            else:
                                logger.warning(f"⚠️ Failed to extract valid price for {store['name']}, keeping old value.")
                        
                        # Sleep to avoid rate limits
                        time.sleep(60)
                        
                    except Exception as e:
                        logger.error(f"Error processing {store['name']}: {e}")

    if updated_count > 0:
        # Create backup
        import shutil
        shutil.copy(json_path, str(json_path) + ".bak_refresh")
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"💾 Saved updates for {updated_count} stores to JSON.")
    else:
        logger.info("No updates were made.")

if __name__ == "__main__":
    main()

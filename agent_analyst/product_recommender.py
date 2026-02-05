import os
import requests
from dotenv import load_dotenv

load_dotenv()

RAKUTEN_APP_ID = os.getenv("RAKUTEN_APP_ID")
RAKUTEN_AFFILIATE_ID = os.getenv("RAKUTEN_AFFILIATE_ID")

def _search_rakuten(keyword):
    """
    Searches items on Rakuten Ichiba using the Item Search API.
    """
    if not RAKUTEN_APP_ID:
        print("WARNING: RAKUTEN_APP_ID is not set.")
        return []

    url = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20170426"
    params = {
        "applicationId": RAKUTEN_APP_ID,
        "affiliateId": RAKUTEN_AFFILIATE_ID,
        "keyword": keyword,
        "format": "json",
        "hits": 3,
        "sort": "reviewCount"
    }

    try:
        response = requests.get(url, params=params)
        data = response.json()
        items = data.get("Items", [])
        
        html_results = []
        for item_wrapper in items:
            item = item_wrapper.get("Item", {})
            name = item.get("itemName")
            price = item.get("itemPrice")
            url = item.get("affiliateUrl")
            image = item.get("mediumImageUrls", [{}])[0].get("imageUrl")
            
            html = f"""
<div class="recommend-box" style="border: 1px border #eee; padding: 15px; margin: 10px 0; border-radius: 8px; display: flex; align-items: center; gap: 15px;">
    <img src="{image}" alt="{name}" style="width: 100px; height: 100px; object-fit: cover;">
    <div>
        <h4 style="margin: 0 0 10px 0; font-size: 16px;">{name}</h4>
        <p style="margin: 0 0 10px 0; font-weight: bold; color: #e44d26;">価格: {price}円</p>
        <a href="{url}" rel="nofollow" target="_blank" style="background: #bf0000; color: #fff; padding: 8px 16px; border-radius: 4px; text-decoration: none; font-size: 14px;">楽天市場で見る</a>
    </div>
</div>
"""
            html_results.append(html)
        return html_results

    except Exception as e:
        print(f"Rakuten search error: {e}")
        return []

def _search_amazon(keyword):
    """
    Placeholder for Amazon Product Advertising API.
    """
    # Requires PA-API keys which are harder to get initially.
    return []

def search_related_items(keyword):
    """
    Combines search results from multiple platforms.
    """
    print(f"Searching products for: {keyword}")
    results = []
    results.extend(_search_rakuten(keyword))
    results.extend(_search_amazon(keyword))
    return results

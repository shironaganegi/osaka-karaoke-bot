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
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code != 200:
            print(f"DEBUG: Rakuten API Error {response.status_code}: {response.text}")
            return []
            
        data = response.json()
        items = data.get("Items", [])
        
        if not items:
            print(f"DEBUG: No items found for keyword '{keyword}' (Rakuten)")
            # Check for API error structure in 200 OK (rare but possible)
            if "error" in data:
                 print(f"DEBUG: API returned error in body: {data}")

        
        html_results = []
        for item_wrapper in items:
            item = item_wrapper.get("Item", {})
            name = item.get("itemName")
            price = item.get("itemPrice")
            url = item.get("affiliateUrl")
            image = item.get("mediumImageUrls", [{}])[0].get("imageUrl")
            
            # Use Markdown instead of HTML for Zenn compatibility
            # Zenn Format:
            # [![Image](ImageURL)](AffiliateURL)
            # [ItemName](AffiliateURL) (Current Price: X Yen)
            
            markdown = f"""
[![{name}]({image})]({url})
[{name}]({url}) (価格: {price}円)
"""
            html_results.append(markdown)
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

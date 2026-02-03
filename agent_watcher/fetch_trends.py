import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def fetch_github_trending(language=None):
    """
    Fetches trending repositories from GitHub.
    Useful for finding new libraries/tools (e.g., 'python', 'javascript', or all).
    """
    url = "https://github.com/trending"
    if language:
        url += f"/{language}"
    
    logging.info(f"Fetching GitHub Trending: {url}")
    try:
        response = requests.get(url)
        response.raise_for_status()
    except Exception as e:
        logging.error(f"Failed to fetch GitHub pages: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    repos = []

    for article in soup.select('article.Box-row'):
        try:
            # Extract basic info
            title_tag = article.select_one('h2 a')
            relative_link = title_tag.get('href')
            full_name = relative_link.strip().lstrip('/')
            owner, repo_name = full_name.split('/')
            url = f"https://github.com{relative_link}"
            
            description_tag = article.select_one('p')
            description = description_tag.get_text(strip=True) if description_tag else "No description"

            # Stats
            stars_tag = article.select_one('a[href$="/stargazers"]')
            stars_text = stars_tag.get_text(strip=True).replace(',', '') if stars_tag else "0"
            stars = int(stars_text)

            # Daily stars (Social Signal)
            daily_stars_tag = article.select_one('span.d-inline-block.float-sm-right')
            daily_stars = 0
            if daily_stars_tag:
                 text = daily_stars_tag.get_text(strip=True)
                 # Format: "123 stars today"
                 daily_stars = int(text.split()[0].replace(',', ''))

            repos.append({
                "source": "github_trending",
                "name": repo_name,
                "owner": owner,
                "url": url,
                "description": description,
                "stars": stars,
                "daily_stars": daily_stars, # Important signal
                "language": language if language else "all",
                "fetched_at": datetime.now().isoformat()
            })
        except Exception as e:
            logging.warning(f"Error parsing a repo: {e}")
            continue

    logging.info(f"Found {len(repos)} repositories.")
    return repos

def fetch_product_hunt():
    """
    Fetches today's top products from Product Hunt.
    Great for discovering new SaaS tools and startups.
    Uses the RSS feed with feedparser for reliability.
    """
    import feedparser
    
    url = "https://www.producthunt.com/feed"
    
    logging.info(f"Fetching Product Hunt RSS: {url}")
    
    try:
        feed = feedparser.parse(url, agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
    except Exception as e:
        logging.error(f"Failed to fetch Product Hunt: {e}")
        return []
    
    products = []
    
    for entry in feed.entries[:10]:  # Top 10
        try:
            name = entry.get('title', 'Unknown')
            link = entry.get('link', '')
            
            # Clean HTML from description
            raw_desc = entry.get('summary', 'New product on Product Hunt')
            desc_soup = BeautifulSoup(raw_desc, 'html.parser')
            clean_desc = desc_soup.get_text()[:200]
            
            products.append({
                "source": "product_hunt",
                "name": name,
                "owner": "ProductHunt",
                "url": link,
                "description": clean_desc,
                "stars": 0,
                "daily_stars": 100,  # Assume high interest for PH products
                "language": "saas",
                "fetched_at": datetime.now().isoformat()
            })
        except Exception as e:
            logging.warning(f"Error parsing Product Hunt item: {e}")
            continue
    
    logging.info(f"Found {len(products)} Product Hunt products.")
    return products



def save_trends(data, filename="trends.json"):
    """Saves the raw trend data to a file."""
    output_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    os.makedirs(output_dir, exist_ok=True)
    
    filepath = os.path.join(output_dir, filename)
    
    # Load existing to append or update? For now, simple overwrite or list append.
    # We want a daily snapshot.
    date_str = datetime.now().strftime("%Y-%m-%d")
    filepath = os.path.join(output_dir, f"trends_{date_str}.json")

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    logging.info(f"Saved trends to {filepath}")

if __name__ == "__main__":
    # 1. Fetch GitHub Trending (General & Python)
    # We target 'python' because the user is a python dev (high affinity)
    # and 'unknown' (general) for viral tools.
    trends_all = fetch_github_trending()
    trends_py = fetch_github_trending("python")
    
    # 2. Fetch Product Hunt (NEW!)
    trends_ph = fetch_product_hunt()
    
    all_data = trends_all + trends_py + trends_ph
    
    # Simple Deduplication
    seen = set()
    unique_data = []
    for item in all_data:
        if item['url'] not in seen:
            unique_data.append(item)
            seen.add(item['url'])
            
    # Save
    save_trends(unique_data)
    logging.info(f"Total unique items saved: {len(unique_data)}")

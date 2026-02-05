from bs4 import BeautifulSoup
from datetime import datetime
from shared.utils import setup_logging, safe_requests_get

logger = setup_logging(__name__)

def fetch_zenn_trends():
    """
    Scrapes trending articles from Zenn.dev tech section.
    """
    url = "https://zenn.dev/articles"
    logger.info(f"Fetching Zenn trends: {url}")
    
    try:
        response = safe_requests_get(url)
        if not response:
            return []

        soup = BeautifulSoup(response.text, 'html.parser')
        
        articles = []
        # Current CSS selector as of Feb 2026 (hypothetical/typical)
        for article in soup.select('article')[:10]:
            title_tag = article.select_one('h2')
            if not title_tag: continue
            
            title = title_tag.get_text(strip=True)
            link_tag = article.select_one('a')
            if not link_tag: continue
            
            url_suffix = link_tag.get('href')
            full_url = f"https://zenn.dev{url_suffix}"
            
            articles.append({
                "source": "zenn",
                "name": title,
                "owner": "Zenn Authors",
                "url": full_url,
                "description": title,
                "stars": 50, # Arbitrary base score for trending
                "daily_stars": 50,
                "language": "japanese",
                "fetched_at": datetime.now().isoformat()
            })
        return articles
    except Exception as e:
        logger.error(f"Failed to fetch Zenn trends: {e}")
        return []

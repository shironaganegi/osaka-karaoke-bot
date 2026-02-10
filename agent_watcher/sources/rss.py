import feedparser
from datetime import datetime
import logging
from shared.utils import setup_logging

logger = setup_logging(__name__)

def fetch_rss_trends(url, name=None):
    """
    Fetches trending topics from an RSS feed.
    """
    if not url:
        return []

    source_name = name if name else "RSS Feed"
    logger.info(f"Fetching RSS: {source_name} ({url})")

    try:
        feed = feedparser.parse(url)
        trends = []

        for entry in feed.entries:
            # Extract basic info
            title = entry.get('title', 'No Title')
            link = entry.get('link', '')
            description = entry.get('summary', '') or entry.get('description', '')
            
            # Simple scoring based on freshness (optional, currently just recent items)
            # RSS doesn't usually have "stars", so we rely on it being news.
            
            # Publish date
            published = entry.get('published', '')
            if not published:
                published = datetime.now().isoformat()

            trends.append({
                "source": "news_feed",
                "source_name": source_name,
                "name": title,
                "url": link,
                "description": description[:200] + "..." if len(description) > 200 else description,
                "daily_stars": 0, # News doesn't have stars, can treat as 0 or boost if needed
                "fetched_at": datetime.now().isoformat()
            })
            
        return trends

    except Exception as e:
        logger.error(f"Error fetching RSS {url}: {e}")
        return []

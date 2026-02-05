import feedparser
from datetime import datetime
from shared.utils import setup_logging

logger = setup_logging(__name__)

def fetch_qiita_trends():
    """
    Fetches trending articles from Qiita via RSS tags.
    Focuses on AI and Python.
    """
    tags = ["python", "ai", "機械学習"]
    results = []
    
    for tag in tags:
        url = f"https://qiita.com/tags/{tag}/feed"
        logger.info(f"Fetching Qiita trends for tag {tag}: {url}")
        
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]: # Top 5 per tag
                results.append({
                    "source": "qiita",
                    "name": entry.title,
                    "owner": entry.author if 'author' in entry else "Qiita User",
                    "url": entry.link,
                    "description": entry.title,
                    "stars": 40, # Base score
                    "daily_stars": 40,
                    "language": "japanese",
                    "fetched_at": datetime.now().isoformat()
                })
        except Exception as e:
            logger.error(f"Failed to fetch Qiita tag {tag}: {e}")
            
    return results

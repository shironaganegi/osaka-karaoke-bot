from datetime import datetime
from shared.utils import setup_logging, safe_requests_get

logger = setup_logging(__name__)

def fetch_hacker_news_trends():
    """
    Fetches top stories from Hacker News and filters for AI/Python tech.
    """
    logger.info("Fetching Hacker News Top Stories")
    try:
        # Get top story IDs
        top_ids_url = "https://hacker-news.firebaseio.com/v0/topstories.json"
        resp_ids = safe_requests_get(top_ids_url)
        top_ids = resp_ids.json() if resp_ids else []
        
        trends = []
        keywords = ["AI", "LLM", "GPT", "Model", "Data", "Python", "Claude", "Gemini"]
        
        # Check first 50 stories for performance
        for story_id in top_ids[:50]:
            story_url = f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
            resp_story = safe_requests_get(story_url, timeout=5)
            if not resp_story:
                continue
            story = resp_story.json()
            
            if not story:
                continue
                
            score = story.get("score", 0)
            title = story.get("title", "")
            
            # Filtering: Score >= 100 and relevant keywords
            if score >= 100 and any(kw.lower() in title.lower() for kw in keywords):
                trends.append({
                    "source": "hacker_news",
                    "name": title,
                    "owner": story.get("by", "Unknown"),
                    "url": story.get("url", f"https://news.ycombinator.com/item?id={story_id}"),
                    "description": title,
                    "stars": score, # Score as a metric
                    "daily_stars": score,
                    "language": "tech",
                    "fetched_at": datetime.now().isoformat()
                })
        
        return trends
    except Exception as e:
        logging.error(f"Failed to fetch Hacker News: {e}")
        return []

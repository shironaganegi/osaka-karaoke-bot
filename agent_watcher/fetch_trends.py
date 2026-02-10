import json
import os
from datetime import datetime
import logging
from shared.config import config
from shared.utils import setup_logging

# Import trend sources
from agent_watcher.sources.github import fetch_github_trending
from agent_watcher.sources.product_hunt import fetch_product_hunt_trends
from agent_watcher.sources.hacker_news import fetch_hacker_news_trends
from agent_watcher.sources.zenn import fetch_zenn_trends
from agent_watcher.sources.qiita import fetch_qiita_trends
from agent_watcher.sources.x_trends import fetch_x_trends
from agent_watcher.sources.rss import fetch_rss_trends

# Setup logging
logger = setup_logging(__name__)

def save_trends(data, x_trends=None, filename_prefix="trends"):
    """Saves the raw trend data to a daily file."""
    output_dir = config.DATA_DIR
    os.makedirs(output_dir, exist_ok=True)
    
    date_str = datetime.now().strftime("%Y-%m-%d")
    filepath = os.path.join(output_dir, f"{filename_prefix}_{date_str}.json")

    final_data = {
        "topics": data,
        "x_hot_words": x_trends or []
    }

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, indent=2, ensure_ascii=False)
    
    logging.info(f"Saved {len(data)} topics and {len(x_trends or [])} X trends to {filepath}")

def load_source_config():
    config_path = os.path.join(os.path.dirname(__file__), "sources_config.json")
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def main():
    """
    Main execution flow to hunt trends from sources defined in config.
    """
    logging.info("--- Project Trend-Hunter Started ---")
    
    # 1. Load Sources Config
    sources = load_source_config()
    all_trends = []

    # Map source types to functions
    source_map = {
        "github": fetch_github_trending,
        "product_hunt": fetch_product_hunt_trends,
        "hacker_news": fetch_hacker_news_trends,
        "zenn": fetch_zenn_trends,
        "qiita": fetch_qiita_trends,
        "news_feed": fetch_rss_trends
    }

    for source in sources:
        sType = source.get("type")
        params = source.get("params", {})
        
        if sType in source_map:
            try:
                logging.info(f"Fetching from {sType} with params {params}...")
                # Dispatch with params if function accepts them
                if sType == "github":
                    trends = source_map[sType](**params)
                else:
                    trends = source_map[sType]() # Others don't take params yet
                
                all_trends.extend(trends)
            except Exception as e:
                logging.error(f"Failed to fetch from {sType}: {e}")

    # Get X trends for viral context (Global context, not a source per se)
    x_hot_words = fetch_x_trends()
    
    # 2. Deduplication based on URL
    seen_urls = set()
    unique_trends = []
    for trend in all_trends:
        if trend["url"] not in seen_urls:
            unique_trends.append(trend)
            seen_urls.add(trend["url"])
            
    # 3. Sort by 'daily_stars' (Ranking signal)
    sorted_trends = sorted(unique_trends, key=lambda x: x.get("daily_stars", 0), reverse=True)
    
    # 4. Save results
    save_trends(sorted_trends, x_trends=x_hot_words)
    logging.info("--- Project Trend-Hunter Completed ---")

if __name__ == "__main__":
    main()

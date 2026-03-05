import requests
import feedparser
import urllib.parse
import sys

# Ensure stdout handles unicode
if sys.stdout.encoding:
    sys.stdout.reconfigure(encoding='utf-8')

def mine_failures(tool_name):
    """
    Searches Reddit for negative feedback, alternatives, and pain points about a tool.
    Returns a summary text.
    """
    # Search queries to find real talk
    queries = [
        f"{tool_name} alternative",
        f"{tool_name} sucks",
        f"{tool_name} problem",
        f"{tool_name} vs"
    ]
    
    found_posts = []
    
    print(f"Mining failure stories for: {tool_name}...")
    
    for query in queries:
        # Use Reddit RSS search (No API key needed for basic scraping)
        encoded_query = urllib.parse.quote(query)
        rss_url = f"https://www.reddit.com/search.rss?q={encoded_query}&sort=relevance&t=year"
        
        try:
            feed = feedparser.parse(rss_url, agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
            
            for entry in feed.entries[:2]: # Get top 2 results per query
                found_posts.append(f"- [Reddit] {entry.title}: {entry.link}")
                
        except Exception as e:
            print(f"Error scraping Reddit: {e}")
            
    if not found_posts:
        return "No significant negative feedback found (or tool is too new)."
        
    return "\n".join(list(set(found_posts))) # Remove duplicates

if __name__ == "__main__":
    # Test
    print(mine_failures("cursor editor"))

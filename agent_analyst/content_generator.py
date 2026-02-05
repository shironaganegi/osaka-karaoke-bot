import os
import json
import requests
import google.generativeai as genai
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from dotenv import load_dotenv
import warnings
import sys
from agent_analyst.failure_miner import mine_failures
from agent_analyst.ad_inventory import AD_CAMPAIGNS
from agent_analyst.product_recommender import search_related_items
from agent_analyst.editor import refine_article
import random

# Suppress deprecation warnings
warnings.filterwarnings("ignore", category=FutureWarning)

# Ensure stdout handles unicode
if sys.stdout.encoding:
    sys.stdout.reconfigure(encoding='utf-8')

# Load environment variables
load_dotenv()

# Configure Gemini
api_key = os.getenv("GEMINI_API_KEY")
if not api_key or api_key.startswith("your_gemini"):
    # Fallback/Mock for demonstration if no key is present or is placeholder
    api_key = None
    print("WARNING: GEMINI_API_KEY is missing or invalid. Using mock generation mode.")
else:
    genai.configure(api_key=api_key)

def get_readme_content(github_url):
    """
    Fetches the README content from a GitHub repository to give context to the LLM.
    """
    try:
        # Convert https://github.com/user/repo -> https://raw.githubusercontent.com/user/repo/main/README.md
        # This is a naive guess, but works for most. 
        # Better robust way is using GitHub API, but lets try raw link for simplicity.
        parts = github_url.strip("/").split("/")
        if len(parts) >= 5:
            user = parts[3]
            repo = parts[4]
            raw_url = f"https://raw.githubusercontent.com/{user}/{repo}/main/README.md"
            
            response = requests.get(raw_url)
            if response.status_code == 200:
                print(f"Retrieved README from {raw_url}")
                return response.text[:10000] # Limit context size
            
            # Try 'master' branch if main fails
            raw_url_master = f"https://raw.githubusercontent.com/{user}/{repo}/master/README.md"
            response = requests.get(raw_url_master)
            if response.status_code == 200:
                return response.text[:10000]

    except Exception as e:
        print(f"Failed to fetch README: {e}")
    
    return "No detailed documentation found."

def generate_article(tool_data):
    """
    Generates a blog post draft using Gemini.
    """
    name = tool_data.get('name')
    description = tool_data.get('description')
    url = tool_data.get('url')
    stars = tool_data.get('stars')
    
    print(f"Analyzing {name}...")
    readme_text = get_readme_content(url)
    
    # NEW: Fetch 'Failure Stories' from Reddit
    failure_context = mine_failures(name)
    
    prompt = f"""
    You are a professional Tech Writer. Write a high-quality blog post in JAPANESE and provide a search keyword for related products.
    
    Product Info:
    - Name: {name} | URL: {url} | Description: {description}
    - Document: {readme_text[:5000]}
    - Feedback: {failure_context}

    Requirements:
    1. Structure: Title, Intro, Features, Install, Pros/Cons, Conclusion.
    2. Placeholder: Insert exactly `{{{{RECOMMENDED_PRODUCTS}}}}` once in the middle of the article (after features).
    3. PR Notice: The very first line after the title must be `> ※本記事はプロモーションを含みます`.

    Output MUST be a valid JSON with two fields:
    - "article": The full markdown article.
    - "search_keyword": A single string (e.g., "Python Beginner Book") to search for related items.
    """

    if not api_key:
        return f"# {name}\n> ※本記事はプロモーションを含みます\nMock content.\n{{{{RECOMMENDED_PRODUCTS}}}}"

    model = genai.GenerativeModel('gemini-1.5-flash')
    try:
        response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        content_text = response.text.strip()
        
        # Handle cases where model might still output markdown code blocks
        if content_text.startswith("```"):
            content_text = content_text.split("```")[1]
            if content_text.startswith("json"):
                content_text = content_text[4:]
        
        try:
            res_json = json.loads(content_text)
        except json.JSONDecodeError:
            # Emergency fallback: Try to treat entire response as article
            print("CRITICAL: Failed to parse JSON. Falling back to raw response.")
            return f"# {name}\n> ※本記事はプロモーションを含みます\n\n{response.text}"

        draft = res_json.get("article", "")
        keyword = res_json.get("search_keyword", name)

        # 1. Search and Inject Products
        try:
            products_html = "".join(search_related_items(keyword))
            # Support both {{ }} and { } just in case
            final_article = draft.replace("{{RECOMMENDED_PRODUCTS}}", products_html).replace("{RECOMMENDED_PRODUCTS}", products_html)
        except Exception as e:
            print(f"Product injection failed: {e}")
            final_article = draft

        # 2. Refine by Editor
        try:
            final_article = refine_article(final_article)
        except Exception as e:
            print(f"Editor refinement failed: {e}")

        # 3. Append Ad Campaign
        try:
            ad = random.choice(AD_CAMPAIGNS)
            final_article += f"\n\n---\n### PR\n{ad['html']}"
        except Exception:
            pass

        return final_article

    except Exception as e:
        print(f"Generation error in generate_draft: {e}")
        import traceback
        traceback.print_exc()
        return f"# {name}\n\n記事の生成中にエラーが発生しました。申し訳ありません。\nエラー詳細: {str(e)}"

def generate_zenn_frontmatter(title, tool_name, source):
    """
    Generates Zenn compatible YAML frontmatter.
    """
    emojis = ["🤖", "🚀", "🛠️", "💻", "💡", "🔥", "📈", "🔍"]
    topics = ["AI", "OpenSource", "Tech", "Programming"]
    if source == "github": topics.append("GitHub")
    if "python" in tool_name.lower(): topics.append("Python")
    
    is_published = os.getenv("ZENN_AUTO_PUBLISH", "false").lower() == "true"
    
    frontmatter = f"""---
title: "{title}"
emoji: "{random.choice(emojis)}"
type: "tech" # tech: 技術記事 / idea: アイデア
topics: {json.dumps(topics)}
published: {str(is_published).lower()}
---

"""
    return frontmatter

def load_history():
    history_path = os.path.join(os.path.dirname(__file__), "..", "data", "history.json")
    if os.path.exists(history_path):
        with open(history_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_to_history(tool_name, url):
    history_path = os.path.join(os.path.dirname(__file__), "..", "data", "history.json")
    history = load_history()
    history.append({
        "name": tool_name,
        "url": url,
        "date": datetime.now().isoformat()
    })
    # Keep only last 100 entries
    history = history[-100:]
    with open(history_path, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

import string

# ... (Imports are fine, keep them)

def load_trends_data():
    """Loads the latest trends JSON file from the data directory."""
    data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    if not os.path.exists(data_dir):
        return []
    
    files = sorted([f for f in os.listdir(data_dir) if f.startswith("trends_")], reverse=True)
    if not files:
        return []
        
    latest_file = os.path.join(data_dir, files[0])
    print(f"Loading data from {latest_file}")
    
    with open(latest_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def select_best_candidate(data):
    """Selects the best tool to write about, considering history and diversity."""
    # 1. Filter usable items (Stars > 0)
    # 2. Apply Cooldown (Exclude if posted in last 14 days)
    history = load_history()
    cooldown_period = timedelta(days=14)
    cutoff_date = datetime.now() - cooldown_period
    
    recent_posted_urls = []
    for h in history:
        try:
            post_date = datetime.fromisoformat(h['date'])
            if post_date > cutoff_date:
                recent_posted_urls.append(h['url'])
        except (ValueError, KeyError):
            continue
            
    candidates = [item for item in data if item.get('daily_stars', 0) > 0 and item['url'] not in recent_posted_urls]
    
    # Fallback if everything is filtered
    if not candidates:
        print("All trending topics were posted recently. Picking a random one from top trends anyway.")
        candidates = [item for item in data if item.get('daily_stars', 0) > 0]
    
    if not candidates:
        return None

    # 3. Ensure Source Diversity (Pick top 2 from each source)
    candidates_by_source = {}
    for item in candidates:
        src = item.get('source', 'unknown')
        if src not in candidates_by_source:
            candidates_by_source[src] = []
        candidates_by_source[src].append(item)
    
    final_pool = []
    for src, items in candidates_by_source.items():
        sorted_items = sorted(items, key=lambda x: x.get('daily_stars', 0), reverse=True)
        final_pool.extend(sorted_items[:2])
        
    print(f"Candidate Poll Size: {len(final_pool)} (Sources: {list(candidates_by_source.keys())})")
    
    # 4. Pick Random Winner
    return random.choice(final_pool)

def save_article_file(content, tool_data):
    """Saves the article to the articles directory with a Zenn-compatible filename."""
    # Generate random 14-char slug
    slug = ''.join(random.choices(string.ascii_lowercase + string.digits, k=14))
    articles_dir = os.path.join(os.path.dirname(__file__), "..", "articles")
    os.makedirs(articles_dir, exist_ok=True)
    
    file_path = os.path.join(articles_dir, f"{slug}.md")
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
        
    # Log to history
    save_to_history(tool_data['name'], tool_data['url'])
    
    print(f"Zenn article saved to: {file_path}")
    print("-" * 30)
    return file_path

if __name__ == "__main__":
    # 1. Load Data
    trends_data = load_trends_data()
    if not trends_data:
        print("No trend data found. Run watcher first.")
        exit()

    # 2. Select Tool
    top_tool = select_best_candidate(trends_data)
    if not top_tool:
        print("No suitable candidates found.")
        exit()

    print(f"Selected Tool: {top_tool['name']} (Source: {top_tool.get('source')})")
    
    # 3. Generate Content
    body_content = generate_article(top_tool)
    
    # 4. Extract Title & Frontmatter
    article_title = "New AI Tool: " + top_tool['name']
    for line in body_content.split("\n"):
        if line.startswith("# "):
            article_title = line.replace("# ", "").replace('"', '\\"')
            break
            
    frontmatter = generate_zenn_frontmatter(article_title, top_tool['name'], top_tool.get('source'))
    final_content = frontmatter + body_content
    
    # 5. Save
    save_article_file(final_content, top_tool)

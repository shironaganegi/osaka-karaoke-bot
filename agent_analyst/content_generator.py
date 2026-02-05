from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import warnings
import sys
from agent_analyst.failure_miner import mine_failures
from agent_analyst.ad_inventory import AD_CAMPAIGNS
from agent_analyst.product_recommender import search_related_items
from agent_analyst.editor import refine_article
from agent_analyst.prompts import ARTICLE_GENERATION_PROMPT
from shared.utils import setup_logging, safe_requests_get, load_config
import random

# Suppress deprecation warnings
warnings.filterwarnings("ignore", category=FutureWarning)

# Ensure stdout handles unicode
if sys.stdout.encoding:
    sys.stdout.reconfigure(encoding='utf-8')

# Load environment variables
load_config()

# Configure Logging
logger = setup_logging(__name__)

# Configure Gemini
api_key = os.getenv("GEMINI_API_KEY")
if not api_key or api_key.startswith("your_gemini"):
    # Fallback/Mock for demonstration if no key is present or is placeholder
    api_key = None
    logger.warning("WARNING: GEMINI_API_KEY is missing or invalid. Using mock generation mode.")
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
            
            response = safe_requests_get(raw_url)
            if response and response.status_code == 200:
                logger.info(f"Retrieved README from {raw_url}")
                return response.text[:10000] # Limit context size
            
            # Try 'master' branch if main fails
            raw_url_master = f"https://raw.githubusercontent.com/{user}/{repo}/master/README.md"
            response = safe_requests_get(raw_url_master)
            if response and response.status_code == 200:
                return response.text[:10000]

    except Exception as e:
        logger.error(f"Failed to fetch README: {e}")
    
    return "No detailed documentation found."

from agent_analyst.prompts import ARTICLE_GENERATION_PROMPT

def generate_article(tool_data, x_hot_words=[]):
    """
    Generates a blog post draft and a viral X post using Gemini.
    """
    name = tool_data.get('name')
    description = tool_data.get('description')
    url = tool_data.get('url')
    
    print(f"Analyzing {name}...")
    readme_text = get_readme_content(url)
    failure_context = mine_failures(name)
    x_context = ", ".join(x_hot_words[:10])
    
    # 1. Prepare Prompt
    prompt = ARTICLE_GENERATION_PROMPT.format(
        nname=name,
        url=url,
        description=description,
        readme_text=readme_text[:5000],
        failure_context=failure_context,
        x_context=x_context
    )

    if not api_key:
        return f"# {name}\n> ※本記事はプロモーションを含みます\nMock content.\n{{{{RECOMMENDED_PRODUCTS}}}}"

    # 2. Call Gemini
    response = call_gemini_with_fallback(prompt)
    if not response:
        return f"# {name}\n\n記事生成に失敗しました（モデルエラー）。"

    # 3. Parse JSON & Extract Content
    try:
        content_text = clean_json_text(response.text)
        res_json = json.loads(content_text)
        
        draft = res_json.get("article", "")
        keywords = res_json.get("search_keywords", [name])
        x_post = res_json.get("x_viral_post", "")
        
    except (json.JSONDecodeError, AttributeError):
        print("CRITICAL: JSON Parsing Failed. Converting raw text.")
        return f"# {name}\n> ※本記事はプロモーションを含みます\n\n{response.text}"

    # 4. Inject Affiliate Products
    final_article = inject_products(draft, keywords)

    # 5. Refine with Editor Personality
    try:
        refined_article = refine_article(final_article)
    except Exception as e:
        print(f"Editor refinement failed: {e}")
        refined_article = final_article

    # 6. Append Ad & X Post
    refined_article = append_footer_content(refined_article, x_post)
    
    return refined_article

def call_gemini_with_fallback(prompt):
    candidate_models = [
        'gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-flash-latest',
        'gemini-2.0-flash-exp', 'gemini-1.5-flash', 'gemini-1.5-pro'
    ]
    for model_name in candidate_models:
        try:
            print(f"Trying model: {model_name}...")
            model = genai.GenerativeModel(model_name)
            return model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        except Exception as e:
            print(f"Model {model_name} failed: {e}")
            continue
    return None

def clean_json_text(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return text.strip()

def inject_products(draft, keywords):
    if isinstance(keywords, str): keywords = [keywords]
    products_html = ""
    
    # Try keywords
    for kw in keywords:
        items = search_related_items(kw)
        if items:
            products_html = "".join(items)
            break
            
    # Fallback
    if not products_html:
        for fb in ["プログラミング 入門", "ガジェット", "Python"]:
            items = search_related_items(fb)
            if items:
                products_html = "".join(items)
                break
                
    return draft.replace("{{RECOMMENDED_PRODUCTS}}", products_html).replace("{RECOMMENDED_PRODUCTS}", products_html)

def append_footer_content(article, x_post):
    # Add Affiliate Campaign
    try:
        ad = random.choice(AD_CAMPAIGNS)
        article += f"\n\n---\n### PR\n{ad['html']}"
    except: pass

    # Add Hidden X Post
    if x_post:
        article += f"\n\n---X_POST_START---\n{x_post}\n---X_POST_END---\n"
    return article

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
    logger.info(f"Loading data from {latest_file}")
    
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
        logger.info("All trending topics were posted recently. Picking a random one from top trends anyway.")
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
        
    logger.info(f"Candidate Poll Size: {len(final_pool)} (Sources: {list(candidates_by_source.keys())})")
    
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
    
    logger.info(f"Zenn article saved to: {file_path}")
    logger.info("-" * 30)
    return file_path

if __name__ == "__main__":
    # 1. Load Data
    trends_data = load_trends_data()
    if not trends_data:
        logger.warning("No trend data found. Run watcher first.")
        exit()

    # Handle new dict format or old list format
    if isinstance(trends_data, dict):
        topics = trends_data.get("topics", [])
        x_hot_words = trends_data.get("x_hot_words", [])
    else:
        topics = trends_data
        x_hot_words = []

    # 2. Select Tool
    top_tool = select_best_candidate(topics)
    if not top_tool:
        logger.warning("No suitable candidates found.")
        exit()

    logger.info(f"Selected Tool: {top_tool['name']} (Source: {top_tool.get('source')})")
    
    # 3. Generate Content
    body_content = generate_article(top_tool, x_hot_words=x_hot_words)
    
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

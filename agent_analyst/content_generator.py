from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import warnings
import sys
import os
import json
import re
import google.generativeai as genai
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
        name=name,
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
        return f"# {name}\n\n記事生成に失敗しました（全てのモデルでエラーまたはタイムアウト）。ログを確認してください。"

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
    
def translate_article_to_english(content):
    """
    Translates the Japanese Markdown content to English using Gemini.
    """
    prompt = f"""
    You are a professional Tech Translator.
    Translate the following Japanese Markdown blog post into high-quality English.
    
    Requirements:
    - Keep the Markdown format exactly as is (headings, links, code blocks).
    - Maintain the professional and insightful tone.
    - Translate "Recommended Products" section naturally (or keep affiliate links if they are universal, otherwise keep them).
    - Do NOT translate the Frontmatter (YAML block at the top), I will handle it programmatically, BUT if you see it, just leave it or ignore it. 
    - Output ONLY the translated markdown content.
    
    Original Content:
    {content}
    """
    
    response = call_gemini_with_fallback(prompt)
    if response:
        return response.text
    return None

def call_gemini_with_fallback(prompt):
    candidate_models = [
        'gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-pro'
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
            
    # Fallback if specific search fails
    if not products_html:
        # Engineer Vocabulary Filter (White-list approach)
        tech_keywords = [
            "Python", "Rust", "Go言語", "AWS", "Docker", "Kubernetes", 
            "React", "TypeScript", "機械学習", "データ分析", "Linux", 
            "Raspberry Pi", "Arduino", "キーボード", "モニター"
        ]
        unique_keywords = set()
        for kw in tech_keywords:
            if kw in draft:
                unique_keywords.add(kw)
        
        # Try finding products for found tech keywords (limit to 2 search attempts)
        for kw in list(unique_keywords)[:2]:
             items = search_related_items(kw)
             if items:
                 products_html += "".join(items)
        
    # Final Fallback to popular gadgets if still empty
    if not products_html:
        # Fallback to popular gadgets (High CTR for tech audience)
        for fb in ["ロジクール マウス", "Anker 充電器", "USB-C ケーブル"]:
            items = search_related_items(fb)
            if items:
                products_html = "".join(items)
                break
        
        # If still nothing (unlikely), specifically use Logicool MX Master 3S keyword
        if not products_html:
             items = search_related_items("MX Master 3S")
             if items: products_html = "".join(items)

    # Emergency Fallback: If API failed completely (e.g. Rate Limit or Network Error)
    # Inject a static internal affiliate link or a reliable banner
    if not products_html:
        products_html = """
<div class="rakuten-item" style="border:1px solid #ddd; padding:15px; margin:20px 0; border-radius:8px; text-align:center;">
    <p style="color:#666; font-size:0.9em; margin-bottom:10px;">👇 エンジニアにおすすめのサービス 👇</p>
    <a href="https://www.onamae.com/" target="_blank" rel="nofollow" style="font-weight:bold; color:#0055aa; font-size:1.1em; text-decoration:none;">
        🌐 独自ドメイン取得なら「お名前.com」。TechTrend Watchも使っています！
    </a>
</div>
"""

    # Wrap in markers for easy removal (e.g. for Qiita)
    # Ensure tighter spacing so Markdown parsers don't treat it as a code block
    wrapped_products = f"\n<!-- AFFILIATE_START -->\n{products_html}\n<!-- AFFILIATE_END -->\n"
    return draft.replace("{{RECOMMENDED_PRODUCTS}}", wrapped_products).replace("{RECOMMENDED_PRODUCTS}", wrapped_products)

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
    
    # CLEANUP: Remove X_POST_START/END block so it doesn't appear in Zenn
    content = re.sub(r'---X_POST_START---[\s\S]*?---X_POST_END---\n?', '', content)

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
    
    if "記事生成に失敗しました" in body_content or "Mock content" in body_content:
        logger.error("Article generation failed. Aborting save.")
        exit(1) # Exit with error code to alert GitHub Actions if needed, or just 0 to skip quietly.
    
    # 4. Extract Title & Frontmatter
    article_title = "New AI Tool: " + top_tool['name']
    for line in body_content.split("\n"):
        if line.startswith("# "):
            article_title = line.replace("# ", "").replace('"', '\\"')
            break
            
    frontmatter = generate_zenn_frontmatter(article_title, top_tool['name'], top_tool.get('source'))
    final_content = frontmatter + body_content
    
    # 5. Save Japanese Article
    filepath_ja = save_article_file(final_content, top_tool)
    
    # 6. Generate & Save English Version
    # Strip Zenn frontmatter for translation to avoid confusion
    body_only = body_content
    logger.info("Translating article to English...")
    
    en_body = translate_article_to_english(body_only)
    if en_body:
        # Create English Frontmatter (Hugo compatible)
        # Note: Zenn frontmatter is not needed for English, but we use a generic md format
        # We will fix frontmatter more properly in distributor, but here we just need content.
        en_content = f"""---
title: "{article_title} (English)"
emoji: "🤖"
type: "tech"
topics: []
published: false
---

{en_body}
"""
        # Save as .en.md
        filename_en = os.path.basename(filepath_ja).replace(".md", ".en.md")
        filepath_en = os.path.join(os.path.dirname(filepath_ja), filename_en)
        
        with open(filepath_en, 'w', encoding='utf-8') as f:
            f.write(en_content)
        logger.info(f"English translation saved to: {filepath_en}")

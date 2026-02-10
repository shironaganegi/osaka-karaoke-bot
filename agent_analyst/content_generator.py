from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import warnings
import sys
import os
import json
import re
import random
import string
import logging

from agent_analyst.failure_miner import mine_failures
from agent_analyst.product_recommender import search_related_items
from agent_analyst.editor import refine_article
from agent_analyst.llm import llm_client
from agent_analyst.affiliate_manager import affiliate_manager
from shared.config import config
from shared.utils import setup_logging, safe_requests_get

# Suppress deprecation warnings
warnings.filterwarnings("ignore", category=FutureWarning)

# Ensure stdout handles unicode
if sys.stdout.encoding:
    sys.stdout.reconfigure(encoding='utf-8')

# Configure Logging
logger = setup_logging(__name__)

def get_readme_content(github_url):
    """
    Fetches the README content from a GitHub repository to give context to the LLM.
    """
    try:
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

def load_ads():
    try:
        with open(config.ADS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load ads from {config.ADS_FILE}: {e}")
        return []

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
    prompt_template = llm_client.load_prompt(os.path.join(config.PROMPTS_DIR, "article_generation.txt"))
    if not prompt_template:
        return f"# {name}\n\nMetrics error: Prompt file missing."

    prompt = prompt_template.format(
        name=name,
        url=url,
        description=description,
        readme_text=readme_text[:5000],
        failure_context=failure_context,
        x_context=x_context
    )

    if not config.GEMINI_API_KEY:
        return f"# {name}\n:::message\n本記事はプロモーションを含みます\n:::\nMock content.\n{{{{RECOMMENDED_PRODUCTS}}}}"

    # 2. Call Gemini
    # Force JSON mode to prevent preamble text
    generation_config = {"response_mime_type": "application/json"}
    
    response_text = ""
    # Retry loop for JSON generation (Content Quality)
    for attempt in range(2):
        response_text = llm_client.generate_content(prompt, generation_config=generation_config)
        
        if not response_text:
            continue
            
        # Quick validation
        if "{" in response_text and "}" in response_text:
            break
        logger.warning(f"Generated content does not look like JSON (Attempt {attempt+1}). Retrying...")

    if not response_text:
        return f"# {name}\n\n記事生成に失敗しました（エラーまたはタイムアウト）。ログを確認してください。"

    # 3. Parse JSON & Extract Content
    try:
        content_text = clean_json_text(response_text)
        res_json = json.loads(content_text)
        
        draft = res_json.get("article", "")
        keywords = res_json.get("search_keywords", [name])
        x_post = res_json.get("x_viral_post", "")
        note_intro = res_json.get("note_intro", "")
        
    except (json.JSONDecodeError, AttributeError) as e:
        logger.error(f"CRITICAL: JSON Parsing Failed: {e}. Raw text len: {len(response_text)}")
        
        # Fallback 1: Try to extract "article" using Regex
        # Look for "article": "..." pattern, handling escaped quotes roughly
        article_match = re.search(r'"article"\s*:\s*"(.*?)",\s*"\w+"', response_text, re.DOTALL)
        if article_match:
            draft = article_match.group(1).replace('\\"', '"').replace('\\n', '\n')
            logger.info("Recovered article content using Regex fallback.")
            keywords = [name]
            x_post = ""
            note_intro = ""
        else:
            # Fallback 2: Treat raw text as article, but strip JSON-like wrappers if present
            # If it starts with {, mostly likely it's a broken JSON.
            # We try to find the largest text block.
            logger.warning("Regex fallback failed. Using raw text as draft.")
            draft = response_text
            keywords = [name]
            x_post = ""
            note_intro = ""

            # Minimal cleanup if it looks like JSON
            if draft.strip().startswith("{") and '"article":' in draft:
                 # Try to strip preamble
                 draft = re.sub(r'^[\s\S]*?"article"\s*:\s*"', '', draft)
                 draft = re.sub(r'",\s*"\w+"[\s\S]*$', '', draft)

    # 4. Inject Affiliate Products
    final_article = inject_products(draft, keywords)

    # 5. Refine with Editor Personality
    try:
        refined_article = refine_article(final_article)
    except Exception as e:
        print(f"Editor refinement failed: {e}")
        refined_article = final_article

    # 6. Append Ad, X Post & Note Intro
    refined_article = append_footer_content(refined_article, x_post, note_intro)
    
    return refined_article
    
def translate_article_to_english(content):
    """
    Translates the Japanese Markdown content to English using Gemini.
    """
    # Pre-processing: Remove Zenn-specific blocks (PR notices etc)
    content = re.sub(r':::message[\s\S]*?:::\n?', '', content)

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
    
    return llm_client.generate_content(prompt)

def clean_json_text(text):
    """
    Robustly extracts JSON object from text using regex.
    Handles cases where text has preambles or markdown code blocks.
    """
    text = text.strip()
    
    # 1. Try to find JSON within code blocks
    code_block_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', text)
    if code_block_match:
        return code_block_match.group(1)
        
    # 2. Try to find the first '{' and the last '}'
    # This handles "Here is the JSON: { ... }"
    json_match = re.search(r'(\{[\s\S]*\})', text)
    if json_match:
        return json_match.group(1)
        
    # 3. Fallback to original cleanup
    return text.strip()

def inject_products(draft, keywords):
    if isinstance(keywords, str): keywords = [keywords]
    
    # Use AffiliateManager to get recommendations (Books -> Rakuten -> Gadgets)
    products_html = affiliate_manager.get_recommendations(draft, keywords)
    
    return draft.replace("{{RECOMMENDED_PRODUCTS}}", products_html).replace("{RECOMMENDED_PRODUCTS}", products_html)

def append_footer_content(article, x_post, note_intro=""):
    # Add Affiliate Campaign
    ads = load_ads()
    try:
        ad = random.choice(ads)
        # Use Zenn message block for cleaner ad separation
        article += f"\n\n:::message\n**おすすめのサービス (PR)**\n\n{ad['html']}\n:::\n"
    except: pass

    # Add Hidden X Post
    if x_post:
        article += f"\n\n---X_POST_START---\n{x_post}\n---X_POST_END---\n"
    
    # Add Hidden Note Intro
    if note_intro:
        article += f"\n\n---NOTE_INTRO_START---\n{note_intro}\n---NOTE_INTRO_END---\n"
        
    return article

def generate_zenn_frontmatter(title, tool_name, source, x_post="", note_intro=""):
    """
    Generates Zenn compatible YAML frontmatter.
    """
    emojis = ["🤖", "🚀", "🛠️", "💻", "💡", "🔥", "📈", "🔍"]
    topics = ["AI", "OpenSource", "Tech", "Programming"]
    if source == "github": topics.append("GitHub")
    if "python" in tool_name.lower(): topics.append("Python")
    
    is_published = config.ZENN_AUTO_PUBLISH
    
    # Escape quotes in metadata
    if x_post: x_post = x_post.replace('"', '\\"').replace("\n", "\\n")
    if note_intro: note_intro = note_intro.replace('"', '\\"').replace("\n", "\\n")

    frontmatter = f"""---
title: "{title}"
emoji: "{random.choice(emojis)}"
type: "tech" # tech: 技術記事 / idea: アイデア
topics: {json.dumps(topics)}
published: {str(is_published).lower()}
x_viral_post: "{x_post}"
note_intro: "{note_intro}"
---

"""
    return frontmatter

def load_history():
    history_path = os.path.join(config.DATA_DIR, "history.json")
    if os.path.exists(history_path):
        with open(history_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_to_history(tool_name, url):
    history_path = os.path.join(config.DATA_DIR, "history.json")
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

def load_trends_data():
    """Loads the latest trends JSON file from the data directory."""
    data_dir = config.DATA_DIR
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

    # Ensure Source Diversity (Pick top 2 from each source)
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
    
    return random.choice(final_pool)

def save_article_file(content, tool_data):
    """Saves the article to the articles directory with a Zenn-compatible filename."""
    
    # Generate random 14-char slug
    slug = ''.join(random.choices(string.ascii_lowercase + string.digits, k=14))
    
    os.makedirs(config.ARTICLES_DIR, exist_ok=True)
    file_path = os.path.join(config.ARTICLES_DIR, f"{slug}.md")
    
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
        exit(1)
    
    # 4. Extract Title & Frontmatter
    article_title = "New AI Tool: " + top_tool['name']
    for line in body_content.split("\n"):
        if line.startswith("# "):
            article_title = line.replace("# ", "").replace('"', '\\"')
            break
            
    # Extract metadata from body_content if still present (legacy fallback) or pass directly
    # In this refactor, we pass them directly from generate_article return if possible,
    # but generate_article currently returns a single string.
    # To avoid changing return signature too much, we will extract them from the returned string specific blocks
    # OR better, change generate_article to return a dict.
    # But for minimal disruption, let's parse them out from the blocks before we remove them.
    
    # Wait, generate_article calls append_footer_content which appends them.
    # We should change generate_article to return (body, metadata)
    # OR we can just pass them to frontmatter generation locally inside generate_article?
    # generate_article returns a string.
    
    # Let's change generate_article to return a tuple: (content, metadata)
    # But that breaks the signature.
    
    # Alternative:
    # 1. generate_article returns the full string with blocks (as before).
    # 2. main() extracts blocks, puts them in frontmatter, and REMOVES them from body.
    
    x_post_match = re.search(r'---X_POST_START---([\s\S]*?)---X_POST_END---', body_content)
    x_viral_post = x_post_match.group(1).strip() if x_post_match else ""
    
    note_intro_match = re.search(r'---NOTE_INTRO_START---([\s\S]*?)---NOTE_INTRO_END---', body_content)
    note_intro = note_intro_match.group(1).strip() if note_intro_match else ""
    
    # Clean body from blocks
    body_content = re.sub(r'---X_POST_START---[\s\S]*?---X_POST_END---\n?', '', body_content)
    body_content = re.sub(r'---NOTE_INTRO_START---[\s\S]*?---NOTE_INTRO_END---\n?', '', body_content)

    frontmatter = generate_zenn_frontmatter(article_title, top_tool['name'], top_tool.get('source'), x_viral_post, note_intro)
    final_content = frontmatter + body_content
    
    # 5. Save Japanese Article
    filepath_ja = save_article_file(final_content, top_tool)
    
    # 6. Generate & Save English Version
    body_only = body_content
    logger.info("Translating article to English...")
    
    en_body = translate_article_to_english(body_only)
    if en_body:
        en_content = f"""---
title: "{article_title} (English)"
emoji: "🤖"
type: "tech"
topics: []
published: false
---

{en_body}
"""
        filename_en = os.path.basename(filepath_ja).replace(".md", ".en.md")
        os.makedirs(config.EN_ARTICLES_DIR, exist_ok=True)
        filepath_en = os.path.join(config.EN_ARTICLES_DIR, filename_en)
        
        with open(filepath_en, 'w', encoding='utf-8') as f:
            f.write(en_content)
        logger.info(f"English translation saved to: {filepath_en}")

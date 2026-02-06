import os
import glob
import re
from atproto import Client
from datetime import datetime
import json
from shared.utils import setup_logging, safe_requests_post, load_config

# Load env variables
load_config()
logger = setup_logging(__name__)

def get_latest_article():
    """Finds the latest article in the Zenn articles directory."""
    articles_dir = os.path.join(os.path.dirname(__file__), "..", "articles")
    files = sorted([f for f in glob.glob(os.path.join(articles_dir, "*.md")) if not f.endswith(".en.md")], key=os.path.getmtime, reverse=True)
    if not files:
        return None
    return files[0]

def parse_article(file_path):
    """Extracts title and body from the Zenn Markdown file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract Title from Frontmatter
    title_match = re.search(r'^title:\s*"(.*)"', content, re.MULTILINE)
    title = title_match.group(1) if title_match else "No Title"
    
    # Extract Body (Remove Frontmatter)
    body = re.sub(r'^---[\s\S]*?---\n', '', content)
    return title, body

def clean_for_qiita(body, zenn_url):
    """
    Removes affiliate links and adds a footer for Qiita.
    Qiita doesn't like affiliate links, so we strip them carefully.
    """
    # 1. Remove "PR" sections (often at the bottom)
    body = re.sub(r'\n### PR[\s\S]*', '', body)

    # 2. Remove Affiliate Product Injection (Targeting the markers)
    body = re.sub(r'<!-- AFFILIATE_START -->[\s\S]*?<!-- AFFILIATE_END -->', '', body)
    
    # 3. Remove "Promotion" disclaimer (Since we removed the ads)
    body = re.sub(r'> ※本記事はプロモーションを含みます\n?', '', body)
    
    # 4. Add canonical link to Zenn
    footer = f"\n\n---\n\n:::note\nこの記事は [Zennで公開された記事]({zenn_url}) の転載です。\n最新情報や詳細な設定方法はZennをご覧ください。\n:::\n"
    
    return body + footer

def post_to_qiita(title, body, tags=None):
    """Posts the article to Qiita."""
    token = os.getenv("QIITA_ACCESS_TOKEN")
    if not token or token.startswith("your_"):
        logger.warning("Qiita token not found or placeholder. Skipping.")
        return None
    
    token = token.strip()

    url = "https://qiita.com/api/v2/items"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # Default tags if none provided
    if not tags:
        tags = [{"name": "AI"}, {"name": "Python"}, {"name": "Tech"}]
    
    payload = {
        "title": title,
        "body": body,
        "tags": tags,
        "private": False # Set to True if you want to verify first
    }
    
    response = safe_requests_post(url, json_data=payload, headers=headers)
    if response and response.status_code == 201:
        logger.info(f"Successfully posted to Qiita: {response.json()['url']}")
        return response.json()['url']
    else:
        logger.error(f"Qiita post failed or returned unexpected status.")
        return None

def post_to_bluesky(text):
    """Posts a short text to BlueSky."""
    handle = os.getenv("BLUESKY_HANDLE")
    password = os.getenv("BLUESKY_PASSWORD")
    
    if not handle or not password:
        logger.warning("BlueSky credentials missing. Skipping.")
        return

    try:
        client = Client()
        client.login(handle, password)
        client.send_post(text)
        logger.info("Successfully posted to BlueSky!")
    except Exception as e:
        logger.error(f"BlueSky Error (Check handle/password?): {e}")

def generate_note_draft(title, zenn_url):
    """
    Generates a draft text for note.mu (targeting general audience).
    Since note has no API, we just format it for manual copy-paste.
    """
    note_title = f"【AI活用】{title} で作業効率が劇的に上がる件"
    note_body = f"""
{note_title}

最近話題のAIツール「{title}」を使ってみました。
これ、エンジニアじゃなくても実はめちゃくちゃ便利なんです。

✅ **ここがすごい！**
- 面倒な作業が自動化できる
- 無料（または低コスト）で始められる
- 今すぐ使える

詳しい使い方や、導入手順は私の技術ブログ（Zenn）で完全解説しています！
興味のある方はぜひチェックしてみてください👇

{zenn_url}

#AI #業務効率化 #副業 #便利ツール
    """
    return note_body.strip()

def send_note_draft_to_discord(note_text):
    """Sends the note draft to Discord for manual posting."""
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        logger.warning("WARNING: DISCORD_WEBHOOK_URL not found. Skipping note draft notification.")
        return

    payload = {
        "username": "AI Affiliate Bot (Note担当)",
        "content": f"**📝 note投稿用ドラフト** (コピペしてnoteに貼ってね！)\n```\n{note_text}\n```"
    }
    
    response = safe_requests_post(webhook_url, json_data=payload)
    if response:
        logger.info("Sent note draft to Discord.")
    else:
        logger.error("Failed to send note draft to Discord.")

def save_hugo_article(title, body, zenn_url, original_file_path, lang="ja", ogp_url=None):
    """
    Saves the article to the Hugo website content directory.
    """
    website_dir = os.path.join(os.path.dirname(__file__), "..", "website", "content", "posts")
    os.makedirs(website_dir, exist_ok=True)
    
    # Generate Hugo Frontmatter
    date_str = datetime.now().isoformat()
    
    # Handle filename suffix for language
    base_name = os.path.basename(original_file_path)
    if lang == "en":
        # expects slug.en.md -> slug.en.md (Hugo handles .en.md automatically)
        target_filename = base_name 
    else:
        # expects slug.md -> slug.md
        target_filename = base_name

    # Extract tags (naive)
    tags = ["AI", "Tools"]
    if "python" in body.lower(): tags.append("Python")
    
    description = f"AIツール「{title}」の活用法を紹介" if lang == "ja" else f"Introduction to {title}"
    
    cover_yaml = ""
    if ogp_url:
        # PaperMod cover image format
        cover_yaml = f"""
cover:
    image: "{ogp_url}"
    alt: "{title}"
    relative: false
"""

    frontmatter = f"""+++
title = "{title}"
date = "{date_str}"
tags = {json.dumps(tags)}
draft = false
description = "{description}"
canonicalUrl = "{zenn_url}"{cover_yaml}
+++

"""
    # Clean body for Hugo
    hugo_body = body.replace("<!-- AFFILIATE_START -->", "").replace("<!-- AFFILIATE_END -->", "")
    
    # Add Footer
    if lang == "ja":
        footer = f"\n\n---\n\n> この記事は [Zenn]({zenn_url}) にも投稿されています。\n"
    else:
        footer = f"\n\n---\n\n> This article was originally published on [Zenn]({zenn_url}) (Japanese).\n"
    
    with open(os.path.join(website_dir, target_filename), 'w', encoding='utf-8') as f:
        f.write(frontmatter + hugo_body + footer)
    
    logger.info(f"Saved Hugo article ({lang}) to: {target_filename}")


def main():
    print("--- Starting Content Distribution ---")

    # Debug: Check Env Vars (Masked)
    print(f"DEBUG: QIITA_ACCESS_TOKEN is set: {'Yes' if os.getenv('QIITA_ACCESS_TOKEN') else 'No'}")
    
    # Find the latest Japanese article
    latest_ja_path = get_latest_article()
    if not latest_ja_path:
        print("No articles found to distribute.")
        return

    # Process Japanese Article (Main Logic)
    title, body = parse_article(latest_ja_path)
    slug = os.path.basename(latest_ja_path).replace(".md", "")
    zenn_url = f"https://zenn.dev/shironaganegi/articles/{slug}"
    
    print(f"Processing (JA): {title}")
    
    # 1. Post to Qiita (JA only)
    try:
        qiita_body = clean_for_qiita(body, zenn_url)
        post_to_qiita(title, qiita_body)
    except Exception as e:
        print(f"Failed to process Qiita distribution: {e}")
    
    # 2. Post to BlueSky (JA)
    try:
        bsky_text = f"📝 新しい記事を書きました！\n\n{title}\n\n#AI #Tech #Zenn\n{zenn_url}"
        post_to_bluesky(bsky_text)
    except Exception as e:
        print(f"Failed to process BlueSky distribution: {e}")

    # 3. Post to X (Using Viral Post Content if available)
    try:
        from agent_publisher.x_publisher import post_to_x
        
        # Extract X Post from article body
        x_post_match = re.search(r'---X_POST_START---([\s\S]*?)---X_POST_END---', body)
        if x_post_match:
            x_viral_text = x_post_match.group(1).strip()
            print("Found viral X post content.")
            post_to_x(custom_text=x_viral_text, article_url=zenn_url)
        else:
            print("No viral X post content found. Fallback to title.")
            fallback_text = f"📝 新着記事: {title}\n\n#AI #Tech\n{zenn_url}"
            post_to_x(custom_text=fallback_text)
            
    except Exception as e:
        print(f"Failed to process X distribution: {e}")

    # 4. Generate OGP Image
    ogp_path = None
    try:
        from agent_publisher.ogp_generator import generate_ogp
        # Use title as catchphrase for now, could be improved
        print("Generating OGP Image...")
        ogp_full_path = generate_ogp(title, "TechTrend Watch")
        if ogp_full_path:
             # Convert absolute path to relative path for Hugo (from content root)
             # Hugo expects images in static/images or similar, but PaperMod 
             # handles page bundles or absolute URL. 
             # For simpler handling in PaperMod without page bundles, 
             # let's assume we copy/move it to static/images/ogp/
             
             website_static_dir = os.path.join(os.path.dirname(__file__), "..", "website", "static", "images", "ogp")
             os.makedirs(website_static_dir, exist_ok=True)
             
             filename = os.path.basename(ogp_full_path)
             new_path = os.path.join(website_static_dir, filename)
             
             import shutil
             shutil.copy2(ogp_full_path, new_path)
             ogp_path = f"/images/ogp/{filename}" # Web path
             print(f"OGP Image ready at: {ogp_path}")
             
    except Exception as e:
        print(f"Failed to generate OGP: {e}")

    # 5. Save to Hugo Website (JA)
    try:
        save_hugo_article(title, body, zenn_url, latest_ja_path, lang="ja", ogp_url=ogp_path)
    except Exception as e:
        logger.error(f"Failed to generate Hugo article (JA): {e}")

    # 4. Process English Article (If exists)
    # Ensure we look for .en.md corresponding to the latest .md
    latest_en_path = latest_ja_path.replace(".md", ".en.md")
    
    if os.path.exists(latest_en_path):
        print(f"Found English translation: {latest_en_path}")
        try:
            # Parse English (Simple, as frontmatter is already clean/minimal)
            with open(latest_en_path, 'r', encoding='utf-8') as f:
                en_content = f.read()
            
            # Extract simple title
            en_title_match = re.search(r'^title:\s*"(.*)"', en_content, re.MULTILINE)
            en_title = en_title_match.group(1) if en_title_match else title
            
            # Clean body (Remove frontmatter)
            en_body = re.sub(r'^---[\s\S]*?---\n', '', en_content)
            
            save_hugo_article(en_title, en_body, zenn_url, latest_en_path, lang="en")
        except Exception as e:
             logger.error(f"Failed to generate Hugo article (EN): {e}")
    else:
        print("No English translation found. Skipping EN distribution.")
    
    print("--- Distribution Completed ---")

if __name__ == "__main__":
    main()

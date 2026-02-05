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
    files = sorted(glob.glob(os.path.join(articles_dir, "*.md")), key=os.path.getmtime, reverse=True)
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

def save_hugo_article(title, body, zenn_url, original_file_path):
    """
    Saves the article to the Hugo website content directory.
    """
    website_dir = os.path.join(os.path.dirname(__file__), "..", "website", "content", "posts")
    os.makedirs(website_dir, exist_ok=True)
    
    # Generate Hugo Frontmatter
    date_str = datetime.now().isoformat()
    slug = os.path.splitext(os.path.basename(original_file_path))[0]
    
    # Extract tags (naive)
    tags = ["AI", "Tools"]
    if "python" in body.lower(): tags.append("Python")
    
    frontmatter = f"""+++
title = "{title}"
date = "{date_str}"
tags = {json.dumps(tags)}
draft = false
description = "AIツール「{title}」の活用法を紹介"
canonicalUrl = "{zenn_url}"
+++

"""
    # Clean body for Hugo
    # Remove the affiliate markers but KEEP the content
    hugo_body = body.replace("<!-- AFFILIATE_START -->", "").replace("<!-- AFFILIATE_END -->", "")
    
    # Add Canonical Link to Zenn (Cross-linking for SEO)
    footer = f"\n\n---\n\n> この記事は [Zenn]({zenn_url}) にも投稿されています。\n"
    
    with open(os.path.join(website_dir, f"{slug}.md"), 'w', encoding='utf-8') as f:
        f.write(frontmatter + hugo_body + footer)
    
    logger.info(f"Saved Hugo article to: {slug}.md")


def main():
    print("--- Starting Content Distribution ---")

    # Debug: Check Env Vars (Masked)
    print(f"DEBUG: QIITA_ACCESS_TOKEN is set: {'Yes' if os.getenv('QIITA_ACCESS_TOKEN') else 'No'}")
    bsky_pass = os.getenv('BLUESKY_PASSWORD')
    print(f"DEBUG: BLUESKY_PASSWORD is set: {'Yes (Length: ' + str(len(bsky_pass)) + ')' if bsky_pass else 'No'}")
    
    article_path = get_latest_article()
    if not article_path:
        print("No articles found to distribute.")
        return

    title, body = parse_article(article_path)
    
    # Assume Zenn URL (You might need to adjust this if you have a custom domain)
    # The slug is the filename without .md
    slug = os.path.basename(article_path).replace(".md", "")
    zenn_url = f"https://zenn.dev/shironaganegi/articles/{slug}"
    
    print(f"Processing: {title}")
    print(f"Zenn URL: {zenn_url}")

    # 1. Post to Qiita
    try:
        qiita_body = clean_for_qiita(body, zenn_url)
        post_to_qiita(title, qiita_body)
    except Exception as e:
        print(f"Failed to process Qiita distribution: {e}")
    
    # 2. Post to BlueSky
    try:
        bsky_text = f"📝 新しい記事を書きました！\n\n{title}\n\n#AI #Tech #Zenn\n{zenn_url}"
        post_to_bluesky(bsky_text)
    except Exception as e:
        print(f"Failed to process BlueSky distribution: {e}")

    # 3. Generate Note Draft (Manual)
    try:
        note_draft = generate_note_draft(title, zenn_url)
        send_note_draft_to_discord(note_draft)
    except Exception as e:
        print(f"Failed to process Note distribution: {e}")

    # 4. Save to Hugo Website (Phase 2)
    try:
        save_hugo_article(title, body, zenn_url, article_path)
    except Exception as e:
        logger.error(f"Failed to generate Hugo article: {e}")
    
    print("--- Distribution Completed ---")

if __name__ == "__main__":
    main()

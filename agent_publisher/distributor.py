import os
import glob
import re
from shared.config import config
from shared.utils import setup_logging

from agent_publisher.platforms.qiita import QiitaPublisher
from agent_publisher.platforms.bluesky import BlueSkyPublisher
from agent_publisher.platforms.twitter import TwitterPublisher
from agent_publisher.platforms.hugo import HugoPublisher
from agent_publisher.platforms.discord import DiscordPublisher

logger = setup_logging(__name__)

def get_latest_article():
    """Finds the latest article in the Zenn articles directory."""
    files = sorted([f for f in glob.glob(os.path.join(config.ARTICLES_DIR, "*.md")) if not f.endswith(".en.md")], key=os.path.getmtime, reverse=True)
    if not files:
        return None
    return files[0]

def parse_article(file_path):
    """Extracts title and body from the Zenn Markdown file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    title_match = re.search(r'^title:\s*"(.*)"', content, re.MULTILINE)
    title = title_match.group(1) if title_match else "No Title"
    
    body = re.sub(r'^---[\s\S]*?---\n', '', content)
    return title, body

def main():
    logger.info("--- Starting Content Distribution ---")

    latest_ja_path = get_latest_article()
    if not latest_ja_path:
        logger.warning("No articles found to distribute.")
        return

    # Process Japanese Article
    title, body = parse_article(latest_ja_path)
    slug = os.path.basename(latest_ja_path).replace(".md", "")
    zenn_url = f"https://zenn.dev/shironaganegi/articles/{slug}"
    
    logger.info(f"Processing (JA): {title}")

    # 1. Qiita
    qiita = QiitaPublisher()
    qiita.publish(title, body, zenn_url)

    # 2. BlueSky
    bsky = BlueSkyPublisher()
    bsky.publish(title, zenn_url)

    # 3. Twitter (X)
    twitter = TwitterPublisher()
    # Extract X Post from article body
    x_post_match = re.search(r'---X_POST_START---([\s\S]*?)---X_POST_END---', body)
    x_viral_text = x_post_match.group(1).strip() if x_post_match else None
    
    twitter.publish(custom_text=x_viral_text, article_url=zenn_url)

    # 4. Hugo (JA)
    hugo = HugoPublisher()
    hugo.save_article(title, body, zenn_url, latest_ja_path, lang="ja")

    # 5. Hugo (EN)
    filename_en = os.path.basename(latest_ja_path).replace(".md", ".en.md")
    latest_en_path = os.path.join(config.EN_ARTICLES_DIR, filename_en)
    
    if os.path.exists(latest_en_path):
        logger.info(f"Found English translation: {latest_en_path}")
        try:
            with open(latest_en_path, 'r', encoding='utf-8') as f:
                en_content = f.read()
            
            en_title_match = re.search(r'^title:\s*"(.*)"', en_content, re.MULTILINE)
            en_title = en_title_match.group(1) if en_title_match else title
            en_body = re.sub(r'^---[\s\S]*?---\n', '', en_content)
            
            hugo.save_article(en_title, en_body, zenn_url, latest_en_path, lang="en")
        except Exception as e:
             logger.error(f"Failed to generate Hugo article (EN): {e}")
    else:
        logger.info("No English translation found. Skipping EN distribution.")

    # Extract Note Intro from article body
    note_intro_match = re.search(r'---NOTE_INTRO_START---([\s\S]*?)---NOTE_INTRO_END---', body)
    note_intro_text = note_intro_match.group(1).strip() if note_intro_match else None

    # 6. Discord Notification
    discord = DiscordPublisher()
    x_text_for_discord = x_viral_text if x_viral_text else f"記事公開: {title}"
    note_text_for_discord = note_intro_text if note_intro_text else "Note用の紹介文はありません。"
    
    discord.notify(title, zenn_url, x_text_for_discord, note_text_for_discord)
    
    logger.info("--- Distribution Completed ---")

if __name__ == "__main__":
    main()

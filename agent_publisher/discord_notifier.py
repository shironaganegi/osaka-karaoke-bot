import os
import glob
import json
import re
from datetime import datetime
from shared.utils import setup_logging, safe_requests_post

logger = setup_logging(__name__)

def send_discord_notification(webhook_url, draft_path=None):
    """
    Sends a notification to Discord when a new draft is created.
    """
    # Find the latest article if not specified
    if not draft_path:
        articles_dir = os.path.join(os.path.dirname(__file__), "..", "articles")
        files = sorted(glob.glob(os.path.join(articles_dir, "*.md")), key=os.path.getmtime, reverse=True)
        if not files:
            logger.info("No articles found to notify about.")
            return
        draft_path = files[0]
    
    filename = os.path.basename(draft_path)
    
    # Read content to extract title and metadata
    with open(draft_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Naive extraction from frontmatter or Markdown
    title = "New Article"
    tool_name = "Tech Tool"
    
    # Try to find YAML title: "..."
    title_match = re.search(r'^title:\s*"(.*)"', content, re.MULTILINE)
    if title_match:
        title = title_match.group(1)
    else:
        # Fallback to # Heading
        for line in content.split("\n"):
            if line.startswith("# "):
                title = line.replace("# ", "")
                break
    
    # Using title as tool_name for simplicity in notification
    tool_name = title.split(":")[0].strip()
    
    # Extract Viral X Post from hidden section
    tweet_text = f"🤖 今日の注目AIツール: {tool_name}\n\n{title}\n\n詳細はこちら！👇\nhttps://zenn.dev/shironaganegi\n\n#AI #Tech #白ネギテック"
    
    x_post_match = re.search(r'---X_POST_START---\n(.*?)\n---X_POST_END---', content, re.DOTALL)
    if x_post_match:
        tweet_text = x_post_match.group(1).strip()
        # Clean the content for Discord embed so it doesn't show the hidden section
        content = content.replace(x_post_match.group(0), "")
    
    # Generate Note Draft
    zenn_url = "https://techtrend-watch.com/posts/" + filename.replace(".md", "") # Updated to new domain
    note_draft = generate_note_draft(title, zenn_url)

    # Create Discord Embed message
    embed = {
        "title": f"📝 新着記事: {tool_name}",
        "description": title[:200],
        "color": 5814783,
        "fields": [
            {"name": "X (旧Twitter) バズりポスト案", "value": f"```\n{tweet_text}\n```", "inline": False},
            {"name": "Note 誘導記事ドラフト", "value": f"```\n{note_draft}\n```", "inline": False},
            {"name": "Generated At", "value": datetime.now().strftime("%Y-%m-%d %H:%M"), "inline": True}
        ],
        "footer": {"text": "AI Affiliate Bot - 魂の1記事"}
    }
 
    payload = {
        "username": "白ネギ・テック編集部",
        "avatar_url": "https://cdn-icons-png.flaticon.com/512/4712/4712109.png",
        "content": "**新しい記事とバズり原稿を用意したぞ！** 🚀",
        "embeds": [embed]
    }
    
    response = safe_requests_post(webhook_url, json_data=payload)
    if response and response.status_code == 204:
        logger.info("Discord notification sent successfully!")
    else:
        logger.error(f"Discord notification failed.")

def generate_note_draft(title, url):
    """
    Generates a draft text for note.mu.
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

詳しい使い方や、導入手順は私の技術ブログ（TechTrend Watch）で完全解説しています！
アフィリエイトリンクもバッチリ貼って収益化も狙えます（笑）

興味のある方はぜひチェックしてみてください👇

{url}

#AI #業務効率化 #副業 #便利ツール
    """
    return note_body.strip()

if __name__ == "__main__":
    # Get webhook URL from environment variable
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    
    if not webhook_url:
        print("ERROR: DISCORD_WEBHOOK_URL environment variable not set.")
        exit(1)
    
    send_discord_notification(webhook_url)


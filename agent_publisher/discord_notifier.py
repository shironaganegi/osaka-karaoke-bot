import os
import requests
import glob
import json
from datetime import datetime

def send_discord_notification(webhook_url, draft_path=None):
    """
    Sends a notification to Discord when a new draft is created.
    """
    # Find the latest draft if not specified
    if not draft_path:
        draft_dir = os.path.join(os.path.dirname(__file__), "..", "drafts")
        files = sorted(glob.glob(os.path.join(draft_dir, "draft_*.md")), key=os.path.getmtime, reverse=True)
        if not files:
            print("No drafts found to notify about.")
            return
        draft_path = files[0]
    
    filename = os.path.basename(draft_path)
    
    # Extract tool name from filename
    try:
        tool_name = filename.split("_", 3)[3].replace(".md", "")
    except IndexError:
        tool_name = "Unknown Tool"
    
    # Read first few lines for preview
    with open(draft_path, 'r', encoding='utf-8') as f:
        content = f.read()
        # Get the title (first # heading)
        title = "New Draft Ready"
        for line in content.split("\n"):
            if line.startswith("# "):
                title = line.replace("# ", "")
                break
    
    # Create Discord Embed message
    embed = {
        "title": f"New Article Draft: {tool_name}",
        "description": title[:200],
        "color": 5814783,  # Blue color
        "fields": [
            {"name": "Tool", "value": tool_name, "inline": True},
            {"name": "Generated At", "value": datetime.now().strftime("%Y-%m-%d %H:%M"), "inline": True}
        ],
        "footer": {"text": "AI Affiliate Bot - Check GitHub for full content"}
    }

    # Tweet Draft for manual posting
    tweet_text = f"🤖 今日の注目AIツール: {tool_name}\n\n{title}\n\n詳細はこちら！👇\nhttps://zenn.dev/shironaganegi\n\n#AI #Tech #白ネギテック"
    
    payload = {
        "username": "AI Affiliate Bot",
        "avatar_url": "https://cdn-icons-png.flaticon.com/512/4712/4712109.png",
        "content": f"**📝 X投稿用ドラフト** (コピペして使ってね！)\n```{tweet_text}```",
        "embeds": [embed]
    }
    
    try:
        response = requests.post(webhook_url, json=payload)
        if response.status_code == 204:
            print("Discord notification sent successfully!")
        else:
            print(f"Discord notification failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Failed to send Discord notification: {e}")

if __name__ == "__main__":
    # Get webhook URL from environment variable
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    
    if not webhook_url:
        print("ERROR: DISCORD_WEBHOOK_URL environment variable not set.")
        exit(1)
    
    send_discord_notification(webhook_url)

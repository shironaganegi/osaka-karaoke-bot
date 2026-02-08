from shared.config import config
from shared.utils import setup_logging, safe_requests_post

logger = setup_logging(__name__)

class DiscordPublisher:
    def __init__(self):
        self.webhook_url = config.DISCORD_WEBHOOK_URL
        if not self.webhook_url:
             logger.warning("Discord Webhook URL missing.")

    def notify(self, title, zenn_url, x_post_text, note_post_text=""):
        if not self.webhook_url:
            return

        embed = {
            "title": "📝 新しい記事を公開しました",
            "url": zenn_url,
            "description": f"[{title}]({zenn_url})",
            "color": 3447003, # Blue
            "fields": [],
            "footer": {
                "text": "TechTrend Watch Bot"
            }
        }

        # Helper to chunk text
        def chunk_text(text, limit=140):
            chunks = []
            while len(text) > limit:
                split_index = text.rfind('\n', 0, limit)
                if split_index == -1: split_index = text.rfind('。', 0, limit)
                if split_index == -1: split_index = limit
                
                chunk = text[:split_index+1]
                if not chunk.strip(): chunk = text[:limit]
                chunks.append(chunk)
                text = text[len(chunk):]
            if text: chunks.append(text)
            return chunks

        # Process X Post
        x_chunks = chunk_text(x_post_text, 140)
        
        # Add URL to LAST chunk if space permits, else new chunk
        # But user wants URL in the post. usually it goes to the last one or first one?
        # Strategy: Put URL in the LAST tweet of the thread.
        # Check if last chunk + url < 140.
        url_text = f"\n\n{zenn_url}"
        if len(x_chunks[-1]) + len(url_text) <= 140:
             x_chunks[-1] += url_text
        else:
             x_chunks.append(url_text.strip())

        for i, chunk in enumerate(x_chunks):
            name = f"X Post ({i+1}/{len(x_chunks)})" if len(x_chunks) > 1 else "X Post"
            if i > 0: name += " (Reply)"
            embed["fields"].append({
                "name": name,
                "value": f"```\n{chunk}\n```"
            })

        # Process Note (Keep as one block usually, but add URL)
        embed["fields"].append({
            "name": "Note Post (Intro)",
            "value": f"```\n{note_post_text}\n\n{zenn_url}\n```"
        })
        
        payload = {
            "username": "AI Affiliate Bot",
            "embeds": [embed]
        }
        
        if safe_requests_post(self.webhook_url, json_data=payload):
            logger.info("Discord notification sent.")
        else:
            logger.error("Failed to send Discord notification.")

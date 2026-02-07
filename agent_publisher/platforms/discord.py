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
            "description": f"[{title}]({zenn_url})",
            "color": 3447003, # Blue
                {
                    "name": "X (Twitter) Post",
                    "value": f"```\n{x_post_text}\n```"
                },
                {
                    "name": "Note Post (Intro)",
                    "value": f"```\n{note_post_text}\n```"
                }
            ],
            "footer": {
                "text": "TechTrend Watch Bot"
            }
        }
        
        payload = {
            "username": "AI Affiliate Bot",
            "embeds": [embed]
        }
        
        if safe_requests_post(self.webhook_url, json_data=payload):
            logger.info("Discord notification sent.")
        else:
            logger.error("Failed to send Discord notification.")

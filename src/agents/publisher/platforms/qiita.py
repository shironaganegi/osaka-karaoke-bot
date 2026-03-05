import os
import requests
import re
from src.shared.config import config
from src.shared.utils import setup_logging, safe_requests_post

logger = setup_logging(__name__)

class QiitaPublisher:
    def __init__(self):
        self.token = config.QIITA_ACCESS_TOKEN

    def publish(self, title, body, zenn_url, tags=None):
        if not self.token or self.token.startswith("your_"):
            logger.warning("Qiita token not found or placeholder. Skipping.")
            return None
        
        token = self.token.strip()
        url = "https://qiita.com/api/v2/items"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # Clean body for Qiita
        body = self._clean_body(body, zenn_url)
        
        if not tags:
            tags = [{"name": "AI"}, {"name": "Python"}, {"name": "Tech"}]
        
        payload = {
            "title": title,
            "body": body,
            "tags": tags,
            "private": False
        }
        
        response = safe_requests_post(url, json_data=payload, headers=headers)
        if response and response.status_code == 201:
            logger.info(f"Successfully posted to Qiita: {response.json()['url']}")
            return response.json()['url']
        else:
            logger.error(f"Qiita post failed.")
            return None

    def _clean_body(self, body, zenn_url):
        # 1. Remove "PR" sections
        body = re.sub(r'\n### PR[\s\S]*', '', body)

        # 2. Remove Affiliate Product Injection
        body = re.sub(r'<!-- AFFILIATE_START -->[\s\S]*?<!-- AFFILIATE_END -->', '', body)
        
        # 3. Remove "Promotion" disclaimer if exact match, or convert message blocks to quotes
        # Convert :::message to blockquotes
        def message_to_quote(match):
            content = match.group(1)
            # Prefix each line with >
            quoted = "\n".join([f"> {line}" for line in content.strip().split("\n")])
            return f"\n{quoted}\n"
            
        body = re.sub(r':::message\n([\s\S]*?)\n:::', message_to_quote, body)
        
        # 5. Add canonical link
        footer = f"\n\n---\n\n> この記事は [TechTrend Watch]({zenn_url}) で公開された記事の転載です。\n> 最新情報や詳細な技術トレンドは公式サイトをご覧ください。\n"
        
        return body + footer

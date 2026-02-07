import os
import requests
import re
from shared.config import config
from shared.utils import setup_logging, safe_requests_post

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
        
        # 3. Remove "Promotion" disclaimer
        body = re.sub(r'> ※本記事はプロモーションを含みます\n?', '', body)
        
        # 5. Add canonical link
        footer = f"\n\n---\n\n:::note\nこの記事は [Zennで公開された記事]({zenn_url}) の転載です。\n最新情報や詳細な設定方法はZennをご覧ください。\n:::\n"
        
        return body + footer

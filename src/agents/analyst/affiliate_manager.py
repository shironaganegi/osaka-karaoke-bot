
import json
import random
import os
from src.agents.analyst.product_recommender import search_related_items
from src.shared.config import config
from src.shared.utils import setup_logging

logger = setup_logging(__name__)

class AffiliateManager:
    def __init__(self):
        self.books_db = self._load_books_db()

    def _load_books_db(self):
        db_path = os.path.join(config.DATA_DIR, "technical_books.json")
        try:
            if os.path.exists(db_path):
                with open(db_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load technical books DB: {e}")
        return {}

    def get_recommendations(self, article_text, keywords, limit=3):
        """
        Returns HTML string of recommended products.
        Priority:
        1. Technical Book matching specific keyword
        2. Rakuten Search for specific keyword
        3. Fallback to generic tech items
        """
        reccomendations = []
        html_output = ""

        # 1. Search for Tech Books first
        found_books = self._search_books(article_text, keywords)
        if found_books:
            logger.info(f"Found related books: {found_books}")
            for book_kw in found_books[:limit]:
                items = search_related_items(book_kw) # Use existing Rakuten search with book title
                if items:
                    html_output += "".join(items)
        
        # If we have enough recommendations, return
        if len(html_output) > 200: # Heuristic check if HTML is populated
             return self._wrap_output(html_output)

        # 2. Tech Keyword Search (Existing logic)
        for kw in keywords[:2]:
             items = search_related_items(kw)
             if items:
                 html_output += "".join(items)
        
        if len(html_output) > 200:
             return self._wrap_output(html_output)

        # 3. Fallback (Gadgets)
        fallback_items = ["ロジクール マウス", "Anker 充電器", "USB-C ケーブル"]
        for fb in fallback_items:
            items = search_related_items(fb)
            if items:
                html_output += "".join(items)
                break
        
        # 4. Emergency Link
        if not html_output:
            html_output = """
### 👇 エンジニアにおすすめのサービス 👇
[**🌐 独自ドメイン取得なら「お名前.com」。TechTrend Watchも使っています！**](https://www.onamae.com/)
"""
        return self._wrap_output(html_output)

    def _search_books(self, text, keywords):
        """Finds specific book titles based on keywords present in text."""
        candidates = []
        text_lower = text.lower()
        
        # Check against DB keys
        for category, books in self.books_db.items():
            # If category name (e.g. "Python") is in text or keywords
            if category.lower() in text_lower or any(category.lower() in k.lower() for k in keywords):
                for book in books:
                    candidates.append(book["keyword"])
        
        # Shuffle to avoid same book every time
        random.shuffle(candidates)
        return candidates

    def _wrap_output(self, html):
        return f"\n<!-- AFFILIATE_START -->\n{html}\n<!-- AFFILIATE_END -->\n"

# Singleton
affiliate_manager = AffiliateManager()

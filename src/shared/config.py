import os
from dotenv import load_dotenv
from dataclasses import dataclass

load_dotenv()

@dataclass(frozen=True)
class Config:
    # API Keys
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    QIITA_ACCESS_TOKEN: str = os.getenv("QIITA_ACCESS_TOKEN", "")
    DISCORD_WEBHOOK_URL: str = os.getenv("DISCORD_WEBHOOK_URL", "")
    
    # BlueSky
    BLUESKY_HANDLE: str = os.getenv("BLUESKY_HANDLE", "")
    BLUESKY_PASSWORD: str = os.getenv("BLUESKY_PASSWORD", "")
    
    # Rakuten
    RAKUTEN_APP_ID: str = os.getenv("RAKUTEN_APP_ID", "")
    RAKUTEN_AFFILIATE_ID: str = os.getenv("RAKUTEN_AFFILIATE_ID", "")
    
    # X (Twitter) - Optional
    X_API_KEY: str = os.getenv("X_API_KEY", "")
    X_API_SECRET: str = os.getenv("X_API_SECRET", "")
    X_ACCESS_TOKEN: str = os.getenv("X_ACCESS_TOKEN", "")
    X_ACCESS_SECRET: str = os.getenv("X_ACCESS_SECRET", "")
    
    # Feature Flags
    ZENN_AUTO_PUBLISH: bool = os.getenv("ZENN_AUTO_PUBLISH", "true").lower() == "true"
    
    # Paths
    # src/shared/config.py → src/ → プロジェクトルート
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    DATA_DIR: str = os.path.join(BASE_DIR, "data")
    ARTICLES_DIR: str = os.path.join(BASE_DIR, "articles")
    EN_ARTICLES_DIR: str = os.path.join(DATA_DIR, "articles_en")
    WEBSITE_CONTENT_DIR: str = os.path.join(BASE_DIR, "website", "content", "posts")
    PROMPTS_DIR: str = os.path.join(DATA_DIR, "prompts")
    ADS_FILE: str = os.path.join(DATA_DIR, "ads.json")
    
    # Constants
    USER_AGENT: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

# Singleton instance
config = Config()

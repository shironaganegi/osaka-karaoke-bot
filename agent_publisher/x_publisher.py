import os
import tweepy
import logging
from dotenv import load_dotenv

load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def post_to_x():
    """
    Posts the latest generated tweet to X (Twitter).
    Free Tier compatible (Text only).
    """
    # 1. Load API Credentials
    consumer_key = os.getenv("X_API_KEY")
    consumer_secret = os.getenv("X_API_SECRET")
    access_token = os.getenv("X_ACCESS_TOKEN")
    access_token_secret = os.getenv("X_ACCESS_TOKEN_SECRET")

    if not all([consumer_key, consumer_secret, access_token, access_token_secret]):
        logging.error("X API credentials are missing. Skipping post.")
        return

    # 2. Setup Client (API v2 for Free Tier)
    client = tweepy.Client(
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        access_token=access_token,
        access_token_secret=access_token_secret
    )

    # 3. Construct the messsage
    # Note: Free Tier allows 1500 tweets/month via API v2.
    post_text = "🤖 今日のAIトレンド情報をお届け！\n\n最新のAIツールや技術記事をまとめました。\n詳細はZennブログで公開予定です！\n\n#AI #Tech #白ネギテック"

    try:
        logging.info("Posting text tweet to X (API v2)...")
        response = client.create_tweet(text=post_text)
        logging.info(f"Successfully posted to X! ID: {response.data['id']}")
        
    except Exception as e:
        logging.error(f"Failed to post to X: {e}")

if __name__ == "__main__":
    post_to_x()

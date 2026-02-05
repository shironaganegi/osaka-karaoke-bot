import os
import tweepy
import glob
import logging
from dotenv import load_dotenv

load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def post_to_x():
    """
    Posts the latest generated tweet and OGP image to X (Twitter).
    """
    # 1. Load API Credentials
    bearer_token = os.getenv("X_BEARER_TOKEN")
    consumer_key = os.getenv("X_API_KEY")
    consumer_secret = os.getenv("X_API_SECRET")
    access_token = os.getenv("X_ACCESS_TOKEN")
    access_token_secret = os.getenv("X_ACCESS_TOKEN_SECRET")

    if not all([consumer_key, consumer_secret, access_token, access_token_secret]):
        logging.error("X API credentials are missing. Skipping post.")
        return

    # 2. Setup Clients (v1.1 for Media upload, v2 for Tweeting)
    auth = tweepy.OAuth1UserHandler(consumer_key, consumer_secret, access_token, access_token_secret)
    api_v1 = tweepy.API(auth)
    client_v2 = tweepy.Client(
        bearer_token=bearer_token,
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        access_token=access_token,
        access_token_secret=access_token_secret
    )

    # 3. Find lateast draft data (Assuming JSON/Markdown contains tweet text)
    # For now, we look for the last generated social post in data/
    # In a real run, this would be passed or read from trends.
    # [Simplified for now: Look for OGP image and a generic message]
    
    image_dir = os.path.join(os.path.dirname(__file__), "..", "data", "images")
    images = sorted(glob.glob(os.path.join(image_dir, "ogp_*.png")), key=os.path.getmtime, reverse=True)
    
    if not images:
        logging.error("No OGP image found to post.")
        return

    latest_image = images[0]
    tool_name = os.path.basename(latest_image).replace("ogp_", "").replace(".png", "")

    # Construct the tweet
    # Note: In a full pipeline, we'd read social_generator.py's output.
    tweet_text = f"🤖 今日の注目のAIツール: {tool_name}\n\n技術ブログを更新しました！\n詳細はこちらからチェックしてください！👇\n\nhttps://zenn.dev/shironaganegi\n\n#AI #Tech #白ネギテック"

    try:
        logging.info(f"Uploading media: {latest_image}")
        media = api_v1.media_upload(filename=latest_image)
        
        logging.info("Posting tweet to X...")
        client_v2.create_tweet(text=tweet_text, media_ids=[media.media_id])
        logging.info("Successfully posted to X!")
        
    except Exception as e:
        logging.error(f"Failed to post to X: {e}")

if __name__ == "__main__":
    post_to_x()

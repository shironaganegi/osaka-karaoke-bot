import tweepy
from shared.config import config
from shared.utils import setup_logging

logger = setup_logging(__name__)

class TwitterPublisher:
    def __init__(self):
        self.client = None
        if all([config.X_API_KEY, config.X_API_SECRET, config.X_ACCESS_TOKEN, config.X_ACCESS_SECRET]):
             self.client = tweepy.Client(
                consumer_key=config.X_API_KEY,
                consumer_secret=config.X_API_SECRET,
                access_token=config.X_ACCESS_TOKEN,
                access_token_secret=config.X_ACCESS_SECRET
            )
        else:
             logger.warning("X API credentials are missing.")

    def publish(self, custom_text=None, article_url=None):
        if not self.client:
            logger.warning("Skipping X post due to missing credentials.")
            return

        if custom_text:
            post_text = custom_text
            if article_url and article_url not in post_text:
                 post_text += f"\n\n{article_url}"
        else:
            post_text = f"🤖 今日のAIトレンド情報をお届け！\n\n詳細はZennブログで公開予定です！\n\n#AI #Tech\n{article_url or ''}"

        try:
        try:
            # Threading Logic
            tweets = []
            
            # Simple chunking by 140 chars (TODO: smarter split by punctuation)
            MAX_LENGTH = 140
            while len(post_text) > MAX_LENGTH:
                # Find a good split point
                split_index = post_text.rfind('\n', 0, MAX_LENGTH)
                if split_index == -1:
                    split_index = post_text.rfind('。', 0, MAX_LENGTH)
                if split_index == -1:
                    split_index = MAX_LENGTH

                chunk = post_text[:split_index+1] # Include the delimiter
                if not chunk.strip(): # Avoid empty chunks if delimiter was at end
                     chunk = post_text[:MAX_LENGTH]
                     
                tweets.append(chunk)
                post_text = post_text[len(chunk):]
            
            if post_text:
                tweets.append(post_text)

            logger.info(f"Posting to X as thread ({len(tweets)} tweets)...")
            
            # Post First Tweet
            first_tweet = self.client.create_tweet(text=tweets[0])
            last_id = first_tweet.data['id']
            logger.info(f"Posted Tweet 1/ {len(tweets)}: ID {last_id}")

            # Post Thread Replies
            for i, text in enumerate(tweets[1:], start=2):
                reply = self.client.create_tweet(text=text, in_reply_to_tweet_id=last_id)
                last_id = reply.data['id']
                logger.info(f"Posted Tweet {i}/{len(tweets)}: ID {last_id}")

        except Exception as e:
            logger.error(f"Failed to post to X: {e}")

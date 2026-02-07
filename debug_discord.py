from agent_publisher.platforms.discord import DiscordPublisher
from shared.utils import setup_logging
import logging

# Configure basic logging to see output
logging.basicConfig(level=logging.INFO)

def test_notify():
    pub = DiscordPublisher()
    
    # Mock data
    title = "Test Article Title"
    zenn_url = "https://zenn.dev/example"
    x_post = "This is a test X post.\nLine 2.\n#Test #AI"
    note_post = "This is a test Note intro.\nIt is calm and professional."
    
    print("Testing Discord Notification...")
    pub.notify(title, zenn_url, x_post, note_post)
    print("Test Call Finished.")

if __name__ == "__main__":
    test_notify()

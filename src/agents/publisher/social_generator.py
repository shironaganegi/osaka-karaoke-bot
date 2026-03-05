import os
import google.generativeai as genai
from dotenv import load_dotenv
import glob
import sys
import warnings

# Suppress deprecation warnings
warnings.filterwarnings("ignore", category=FutureWarning)

# Ensure stdout handles unicode
if sys.stdout.encoding:
    sys.stdout.reconfigure(encoding='utf-8')

# Load environment variables
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key or api_key.startswith("your_gemini"):
    print("WARNING: GEMINI_API_KEY is missing. Cannot generate tweets.")
    exit()

genai.configure(api_key=api_key)

def generate_tweet_thread(draft_content):
    """
    Generates a viral-style Twitter thread from the blog post content.
    """
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = f"""
    You are a professional Social Media Manager for a tech news account.
    Create a highly engaging Twitter (X) thread (3-5 tweets) based on the following blog post draft.
    
    **Goal**: Drive clicks to the blog post (assume the link is [LINK]).
    **Target**: Japanese Engineers & Tech Enthusiasts.
    **Tone**: Urgent, Exciting, insightful. Use Emojis effectively.
    
    **Content**:
    {draft_content[:6000]}
    
    **Rules**:
    1. First tweet must have a "Hook" that stops the scroll.
    2. Don't sound like a bot. Sound like a knowledgeable human.
    3. Include 3 relevant hashtags (e.g. #AI #Python).
    4. Output format:
       [Tweet 1]
       ...
       [Tweet 2]
       ...
    """
    
    response = model.generate_content(prompt)
    return response.text

if __name__ == "__main__":
    # 1. Find the latest draft
    draft_dir = os.path.join(os.path.dirname(__file__), "..", "drafts")
    files = sorted(glob.glob(os.path.join(draft_dir, "draft_*.md")), key=os.path.getmtime, reverse=True)
    
    if not files:
        print("No drafts found. Run analyst agent first.")
        exit()
        
    latest_draft = files[0]
    print(f"Generating tweets for: {os.path.basename(latest_draft)}")
    
    with open(latest_draft, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # 2. Generate Thread
    tweets = generate_tweet_thread(content)
    
    # 3. Save Tweets (Simulate Draft)
    base_name = os.path.basename(latest_draft).replace("draft_", "tweets_").replace(".md", ".txt")
    output_path = os.path.join(draft_dir, base_name)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(tweets)
        
    print(f"✅ Tweets saved to: {output_path}")
    print("-" * 30)
    print(tweets)

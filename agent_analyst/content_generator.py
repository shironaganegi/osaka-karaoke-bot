import os
import json
import requests
import google.generativeai as genai
from bs4 import BeautifulSoup
from datetime import datetime
from dotenv import load_dotenv
import warnings
import sys

# Suppress deprecation warnings
warnings.filterwarnings("ignore", category=FutureWarning)

# Ensure stdout handles unicode
if sys.stdout.encoding:
    sys.stdout.reconfigure(encoding='utf-8')

# Load environment variables
load_dotenv()

# Configure Gemini
api_key = os.getenv("GEMINI_API_KEY")
if not api_key or api_key.startswith("your_gemini"):
    # Fallback/Mock for demonstration if no key is present or is placeholder
    api_key = None
    print("WARNING: GEMINI_API_KEY is missing or invalid. Using mock generation mode.")
else:
    genai.configure(api_key=api_key)

def get_readme_content(github_url):
    """
    Fetches the README content from a GitHub repository to give context to the LLM.
    """
    try:
        # Convert https://github.com/user/repo -> https://raw.githubusercontent.com/user/repo/main/README.md
        # This is a naive guess, but works for most. 
        # Better robust way is using GitHub API, but lets try raw link for simplicity.
        parts = github_url.strip("/").split("/")
        if len(parts) >= 5:
            user = parts[3]
            repo = parts[4]
            raw_url = f"https://raw.githubusercontent.com/{user}/{repo}/main/README.md"
            
            response = requests.get(raw_url)
            if response.status_code == 200:
                print(f"Retrieved README from {raw_url}")
                return response.text[:10000] # Limit context size
            
            # Try 'master' branch if main fails
            raw_url_master = f"https://raw.githubusercontent.com/{user}/{repo}/master/README.md"
            response = requests.get(raw_url_master)
            if response.status_code == 200:
                 return response.text[:10000]

    except Exception as e:
        print(f"Failed to fetch README: {e}")
    
    return "No detailed documentation found."

def generate_article(tool_data):
    """
    Generates a blog post draft using Gemini.
    """
    name = tool_data.get('name')
    description = tool_data.get('description')
    url = tool_data.get('url')
    stars = tool_data.get('stars')
    
    print(f"Analyzing {name}...")
    readme_text = get_readme_content(url)
    
    prompt = f"""
    You are a professional Tech Writer specializing in AI tools. 
    Write a high-quality, engaging blog post draft in JAPANESE about the following new AI tool.
    
    Target Audience: Japanese AI Engineers and Python Beginners.
    Tone: Professional, Excited, Informative (E-E-A-T focused).

    Product Info:
    - Name: {name}
    - URL: {url}
    - Description: {description}
    - Current Stars: {stars} (Trending now!)
    - Technical Documentation (Context):
    {readme_text}

    Structure Requirements:
    1. **Catchy Title**: Include "AI" and a benefit (e.g., "Productivity x10").
    2. **Introduction**: Why is this tool getting popular? (Mention the star count).
    3. **What is it?**: Explain simply for beginners.
    4. **Key Features**: strict bullet points based on the README.
    5. **How to Install**: Python pip command or similar.
    6. **Pro's & Con's (Honest Review)**: Imagine you used it. What are the likely limitations?
    7. **Conclusion**: Who should use this?

    Output Format: Markdown.
    """

    if not api_key:
        return f"""
# [Mock] {name}: The Future of AI Coding?
*(API Key missing, this is a placeholder draft)*

## Intro
{name} is trending with {stars} stars today.

## Description
{description}

## Context
{readme_text[:200]}...
        """

    model = genai.GenerativeModel('gemini-2.5-flash')
    response = model.generate_content(prompt)
    return response.text

if __name__ == "__main__":
    # 1. Load the latest trends data
    data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    # Find the most recent json file
    files = sorted([f for f in os.listdir(data_dir) if f.startswith("trends_")], reverse=True)
    
    if not files:
        print("No trend data found. Run watcher first.")
        exit()
        
    latest_file = os.path.join(data_dir, files[0])
    print(f"Loading data from {latest_file}")
    
    with open(latest_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 2. Pick the Winner (Top Daily Stars)
    # Filter for items with daily_stars > 0
    candidates = [item for item in data if item.get('daily_stars', 0) > 0]
    if not candidates:
        candidates = data # fallback
        
    top_tool = sorted(candidates, key=lambda x: x.get('daily_stars', 0), reverse=True)[0]
    
    # 3. Generate Draft
    draft_content = generate_article(top_tool)
    
    # 4. Save Draft
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    safe_name = top_tool['name'].replace(" ", "_")
    draft_filename = f"draft_{timestamp}_{safe_name}.md"
    draft_path = os.path.join(os.path.dirname(__file__), "..", "drafts", draft_filename)
    
    with open(draft_path, 'w', encoding='utf-8') as f:
        f.write(draft_content)
        
    print(f"Draft saved to: {draft_path}")
    print("-" * 30)
    # print(draft_content[:500] + "...\n(truncated)") # Disable printing to avoid console encoding errors

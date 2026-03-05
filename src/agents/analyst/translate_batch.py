import os
import glob
import time
import re
from src.agents.analyst.content_generator import translate_article_to_english
from src.shared.utils import load_config

# Load env variables (API keys etc)
load_config()

def generate_english_for_existing():
    # Define articles directory
    articles_dir = os.path.join(os.path.dirname(__file__), "..", "articles")
    
    # Get all .md files that are NOT .en.md and not random files
    files = [f for f in glob.glob(os.path.join(articles_dir, "*.md")) 
             if not f.endswith(".en.md") and os.path.basename(f) != ".gitkeep"]
    
    print(f"Found {len(files)} Japanese articles.")

    for file_path in files:
        base_name = os.path.basename(file_path)
        en_file_path = file_path.replace(".md", ".en.md")
        
        # Skip if already exists
        if os.path.exists(en_file_path):
            print(f"Skipping {base_name} (EN already exists)")
            continue
            
        print(f"Translating {base_name}...")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # 1. Translate content
            en_body = translate_article_to_english(content)
            
            if en_body:
                # 2. Extract Title from original frontmatter
                title = "Tech Report"
                title_match = re.search(r'^title:\s*"(.*)"', content, re.MULTILINE)
                if title_match:
                    title = title_match.group(1) + " (English)"
                
                # 3. Create EN Frontmatter
                en_frontmatter = f"""---
title: "{title}"
emoji: "🤖"
type: "tech"
topics: []
published: false
---

"""
                # Combine (Ensure en_body doesn't have frontmatter duplicated if model added it)
                # Remove potential triple backticks or "markdown" label
                clean_body = re.sub(r'^```markdown\s*', '', en_body, flags=re.MULTILINE)
                clean_body = re.sub(r'```\s*$', '', clean_body, flags=re.MULTILINE)
                
                en_full_content = en_frontmatter + clean_body.strip()

                # 4. Save
                with open(en_file_path, 'w', encoding='utf-8') as f:
                    f.write(en_full_content)
                print(f"✅ Saved {en_file_path}")
                
                # Sleep to respect rate limits (Free tier: 15 RPM)
                time.sleep(10)
            else:
                print(f"❌ Failed to translate {base_name} (Empty response)")
                
        except Exception as e:
            print(f"❌ Error processing {base_name}: {e}")

if __name__ == "__main__":
    generate_english_for_existing()

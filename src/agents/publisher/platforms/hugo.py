import os
import json
import re
from datetime import datetime
from src.shared.config import config
from src.shared.utils import setup_logging

logger = setup_logging(__name__)

class HugoPublisher:
    def save_article(self, title, body, zenn_url, original_filename, lang="ja", ogp_url=None):
        os.makedirs(config.WEBSITE_CONTENT_DIR, exist_ok=True)
        
        date_str = datetime.now().isoformat()
        target_filename = os.path.basename(original_filename)

        tags = ["AI", "Tools"]
        if "python" in body.lower(): tags.append("Python")
        
        description = f"AIツール「{title}」の活用法を紹介" if lang == "ja" else f"Introduction to {title}"
        
        cover_yaml = ""
        # Disabled OGP logic placeholder
        
        frontmatter = f"""+++
title = "{title}"
date = "{date_str}"
tags = {json.dumps(tags)}
draft = false
description = "{description}"
canonicalUrl = "{zenn_url}"{cover_yaml}
+++

"""
        # Clean body for Hugo
        hugo_body = body.replace("<!-- AFFILIATE_START -->", "").replace("<!-- AFFILIATE_END -->", "")
        hugo_body = re.sub(r'---X_POST_START---[\s\S]*?---X_POST_END---\n?', '', hugo_body)
        hugo_body = re.sub(r'---NOTE_INTRO_START---[\s\S]*?---NOTE_INTRO_END---\n?', '', hugo_body)

        # Convert Zenn syntax (:::message) to blockquotes
        def message_to_quote(match):
            content = match.group(1)
            # Prefix each line with >
            quoted = "\n".join([f"> {line}" for line in content.strip().split("\n")])
            return f"\n{quoted}\n"
            
        hugo_body = re.sub(r':::message\n([\s\S]*?)\n:::', message_to_quote, hugo_body)
        
        if lang == "ja":
            # No footer needed for main site (or maybe affiliate disclaimer if wanted)
            footer = "" 
        else:
            footer = f"\n\n---\n\n> This article is also available in [Japanese]({zenn_url}).\n" # Actually zenn_url is now website_url so this links to JA version on same site

        
        output_path = os.path.join(config.WEBSITE_CONTENT_DIR, target_filename)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(frontmatter + hugo_body + footer)
        
        logger.info(f"Saved Hugo article ({lang}) to: {output_path}")

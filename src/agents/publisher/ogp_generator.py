import os
import glob
import re
import sys
from playwright.sync_api import sync_playwright

# Ensure stdout handles unicode
if sys.stdout.encoding:
    sys.stdout.reconfigure(encoding='utf-8')

def generate_ogp(tool_name, catchphrase):
    """
    Generates an OGP image for the given tool name.
    """
    template_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "ogp_template.html"))
    output_dir = os.path.join(os.path.dirname(__file__), "..", "data", "images")
    os.makedirs(output_dir, exist_ok=True)
    
    # Sanitize filename (remove colons, slashes, etc.)
    safe_name = re.sub(r'[\\/:*?"<>|]', '_', tool_name)
    output_path = os.path.join(output_dir, f"ogp_{safe_name}.png")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1200, "height": 630})
        
        # Load the local HTML file
        page.goto(f"file:///{template_path}")
        
        # Inject dynamic content (JavaScript)
        page.eval_on_selector("#tool-name", f"el => el.textContent = '{tool_name}'")
        page.eval_on_selector("#catchphrase", f"el => el.textContent = '{catchphrase}'")
        
        # Take screenshot
        page.screenshot(path=output_path)
        browser.close()
        
    print(f"OGP Image saved to: {output_path}")
    return output_path

if __name__ == "__main__":
    # Find the latest draft
    draft_dir = os.path.join(os.path.dirname(__file__), "..", "drafts")
    files = sorted(glob.glob(os.path.join(draft_dir, "draft_*.md")), key=os.path.getmtime, reverse=True)
    
    if not files:
        print("No drafts found.")
        exit()
        
    latest_draft = files[0]
    filename = os.path.basename(latest_draft)
    
    # Extract Tool Name from filename (e.g. draft_2026..._toolname.md)
    # Assumes format: draft_YYYYMMDD_HHMM_tool-name.md
    try:
        tool_name = filename.split("_", 3)[3].replace(".md", "")
    except IndexError:
        tool_name = "Unknown Tool"

    # Extract Title (Catchphrase) from the first line of the file # Title
    catchphrase = "AI Tool Report"
    with open(latest_draft, 'r', encoding='utf-8') as f:
        first_line = f.readline().strip()
        if first_line.startswith("# "):
            catchphrase = first_line.replace("# ", "")

    print(f"Generating OGP for: {tool_name}")
    generate_ogp(tool_name, catchphrase)

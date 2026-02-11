from playwright.sync_api import sync_playwright

url = "https://www.karaokemanekineko.jp/locations/osaka/osaka-shi/namba-hips-store/"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(url)
    page.wait_for_timeout(3000) # Wait for JS to load
    
    content = page.content()
    with open("debug_manekineko.html", "w", encoding="utf-8") as f:
        f.write(content)
    
    print("Saved HTML to debug_manekineko.html")
    browser.close()

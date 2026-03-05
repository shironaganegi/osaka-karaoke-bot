
import requests
import re
from bs4 import BeautifulSoup
import sys

# 調査対象: 阪急東通り店（ここさえ分かれば他も同じ構造のはず）
TARGET_URL = "https://www.karaokemanekineko.jp/locations/osaka/osaka-shi/hankyu-higashidori-store/"

def analyze_page():
    print(f"Analyzing: {TARGET_URL}")
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
        res = requests.get(TARGET_URL, headers=headers, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')

        print("\n--- PDF Links Found ---")
        pdfs = soup.find_all('a', href=re.compile(r'\.pdf$', re.I))
        if not pdfs:
            print("No PDF links found.")
        else:
            for i, a in enumerate(pdfs):
                url = a.get('href')
                text = a.get_text(strip=True)
                if url and not url.startswith('http'):
                    if url.startswith('/'):
                        url = "https://www.karaokemanekineko.jp" + url
                    else:
                        # Assuming relative to current path structure or root, usually root for these sites
                        url = "https://www.karaokemanekineko.jp/" + url 
                print(f"[{i+1}] Text: {text} | URL: {url}")

        print("\n--- Image Links (Potential Price Lists) ---")
        # 'price', 'charge', 'ryokin', 'table', '料金' が含まれる画像を探す
        imgs = soup.find_all('img')
        found_img = False
        keywords = ['price', 'charge', 'ryokin', 'table', '料金']
        
        for img in imgs:
            src = img.get('src', '')
            alt = img.get('alt', '') or ''
            
            # Check if src or alt contains any keyword
            if any(k in src.lower() or k in alt.lower() for k in keywords):
                if src and not src.startswith('http'):
                    if src.startswith('/'):
                        src = "https://www.karaokemanekineko.jp" + src
                    else:
                        src = "https://www.karaokemanekineko.jp/" + src
                print(f"Image: {src} | Alt: {alt}")
                found_img = True
        
        if not found_img:
            print("No obvious price-list images found matching keywords.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    analyze_page()

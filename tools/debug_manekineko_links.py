import requests
from bs4 import BeautifulSoup
import sys

TARGETS = [
    ("梅田芝田店", "https://www.karaokemanekineko.jp/locations/osaka/osaka-shi/umeda-shibata-store/"),
    ("茶屋町店", "https://www.karaokemanekineko.jp/locations/osaka/osaka-shi/chayamachi-store/"),
    ("阪急東通り2号店", "https://www.karaokemanekineko.jp/locations/osaka/osaka-shi/hankyuhigashidori-2nd-store/")
]

def check_pdfs():
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    for name, url in TARGETS:
        print(f"\n--- {name} ---")
        print(f"URL: {url}")
        try:
            res = requests.get(url, headers=headers, timeout=10)
            res.raise_for_status() # Check for HTTP errors
            soup = BeautifulSoup(res.text, 'html.parser')

            # PDFリンクを探す
            pdfs = soup.find_all('a', href=lambda x: x and x.lower().endswith('.pdf'))
            if not pdfs:
                print("❌ No PDF links found.")
            for a in pdfs:
                link = a['href']
                if not link.startswith('http'): 
                    if link.startswith('/'):
                        link = "https://www.karaokemanekineko.jp" + link
                    else:
                        link = "https://www.karaokemanekineko.jp/" + link
                print(f"Found: {link} (Text: {a.get_text(strip=True)})")
                
            # 画像も探す
            imgs = soup.find_all('img')
            found_img = False
            for img in imgs:
                src = img.get('src', '')
                alt = img.get('alt', '')
                if '料金' in alt or 'price' in src:
                    if src and not src.startswith('http'):
                        if src.startswith('/'):
                            src = "https://www.karaokemanekineko.jp" + src
                        else:
                            src = "https://www.karaokemanekineko.jp/" + src
                    print(f"Image: {src} (Alt: {alt})")
                    found_img = True
            
            if not found_img:
                print("No obvious price images found.")
                    
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    check_pdfs()

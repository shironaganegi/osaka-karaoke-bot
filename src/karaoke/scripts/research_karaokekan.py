import requests
from bs4 import BeautifulSoup

def search_karaokekan_osaka():
    url = "https://karaokekan.jp/shop/osaka"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        resp = requests.get(url, headers=headers)
        resp.encoding = resp.apparent_encoding
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # 店舗リストのセレクタ（仮）を推測して抽出
        # 実際にはサイトを見て調整が必要だが、まずはリンク一覧を探す
        shops = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.text.strip()
            if "/shop/osaka/" in href:
                shops.append({"name": text, "url": "https://karaokekan.jp" + href if href.startswith("/") else href})
        
        print(f"Found {len(shops)} potential shops in Osaka.")
        for s in shops[:5]:
            print(f"- {s['name']}: {s['url']}")
            
        return shops
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    search_karaokekan_osaka()

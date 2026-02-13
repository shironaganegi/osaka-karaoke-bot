"""
まねきねこPDF料金表スクレイピング (Chain of Thought強化版 + キャッシュ機能)
=====================================================
"""

import requests
import pdfplumber
import re
import json
import io
import sys
import time
import os
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai
from bs4 import BeautifulSoup

# .envファイルの読み込み
load_dotenv()

# ターゲット店舗リスト
TARGET_STORES = [
    {
        "name": "カラオケまねきねこ 阪急東通り店",
        "url": "https://www.karaokemanekineko.jp/locations/osaka/osaka-shi/hankyu-higashidori-store/"
    },
    {
        "name": "カラオケまねきねこ 梅田芝田店",
        "url": "https://www.karaokemanekineko.jp/locations/osaka/osaka-shi/umeda-shibata-store/"
    },
    {
        "name": "カラオケまねきねこ 茶屋町店",
        "url": "https://www.karaokemanekineko.jp/locations/osaka/osaka-shi/chayamachi-store/"
    },
    {
        "name": "カラオケまねきねこ 阪急東通り2号店",
        "url": "https://www.karaokemanekineko.jp/locations/osaka/osaka-shi/hankyuhigashidori-2nd-store/"
    }
]

def fetch_pdf_url(store_url):
    """BeautifulSoupを使用してPDFリンクを確実に取得"""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(store_url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # .pdf を含むリンクを全て探す
        links = soup.find_all('a', href=re.compile(r'\.pdf$', re.I))
        
        for link in links:
            url = link.get('href')
            if not url: continue
            
            # 相対パスなら絶対パスに
            if not url.startswith('http'):
                url = "https://www.karaokemanekineko.jp" + url
            
            # CloudFrontなどのURLも許可
            return url
            
        return None
    except Exception as e:
        print(f"Error fetching HTML for {store_url}: {e}", file=sys.stderr)
        return None

def download_pdf(pdf_url):
    try:
        response = requests.get(pdf_url, timeout=15)
        response.raise_for_status()
        return response.content
    except Exception as e:
        print(f"Error downloading PDF {pdf_url}: {e}", file=sys.stderr)
        return None

def extract_prices_with_gemini(pdf_bytes):
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("Error: GOOGLE_API_KEY not found.", file=sys.stderr)
        return None

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            if not pdf.pages: return None
            
            # 1ページ目のみ解析（通常ここにメイン料金がある）
            page = pdf.pages[0]
            im = page.to_image(resolution=300)
            target_image = im.original
            
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-2.0-flash') # 高性能モデル指定
            
            # 思考プロセスを含めたプロンプト
            prompt = """
            あなたはカラオケ料金の専門家です。この画像の料金表から、以下の条件に合う「数値」を正確に抽出してください。
            表は複雑で、学生・シニア・会員・非会員・朝うた・ゼロカラなどの情報が混在しています。

            ## 思考ステップ
            1. 表の「列（横軸）」を確認し、「一般会員（Member）」の列を見つける。※学生やシニアではない。
            2. 表の「行（縦軸）」を確認し、「昼（OPEN〜18:00頃）」の行を見つける。
            3. その交差するセルの「30分料金」と「フリータイム料金」を読む。
            4. 「ワンドリンク制(+Order)」か「ドリンクバー付」かは問わず、表示されている金額（室料）をそのまま抽出する。
            5. 土日祝(Weekend)ではなく、**平日(Weekday)** の料金を優先する。

            ## 出力フォーマット (JSONのみ)
            ```json
            {
                "reasoning": "表の左側にある時間帯... 会員列の...",
                "weekday_30min": 数値,
                "weekday_free_time": 数値 または null
            }
            ```
            ※数値が見つからない場合は null。文字（"円"など）は削除して数値のみにする。
            """

            response = model.generate_content([prompt, target_image])
            text = response.text.replace("```json", "").replace("```", "").strip()
            
            try:
                data = json.loads(text)
                print(f"  🤖 AI Thinking: {data.get('reasoning')}", file=sys.stderr)
                return data
            except json.JSONDecodeError:
                print(f"  Failed to parse JSON: {text}", file=sys.stderr)
                return None

    except Exception as e:
        print(f"Error in Gemini: {e}", file=sys.stderr)
        return None

def main():
    # キャッシュデータの読み込み
    json_path = "data/stations_with_prices.json"
    cache_map = {}
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for station, stores in data.get("stations", {}).items():
                    for store in stores:
                        # 検索用に正規化
                        norm_name = store.get("name", "").replace(" ", "").replace("　", "")
                        cache_map[norm_name] = store
        except Exception as e:
            print(f"Warning: Failed to load cache: {e}", file=sys.stderr)

    results = []
    print("[", file=sys.stdout)
    first = True

    for store in TARGET_STORES:
        print(f"Processing {store['name']}...", file=sys.stderr)
        pdf_url = fetch_pdf_url(store['url'])
        
        pricing_data = {"status": "failed"}
        
        # キャッシュチェック
        norm_target = store['name'].replace(" ", "").replace("　", "")
        cached_store = cache_map.get(norm_target)
        
        # 部分一致検索 (キャッシュマップにない場合)
        if not cached_store:
             for k, v in cache_map.items():
                if norm_target in k or k in norm_target:
                    if "まねきねこ" in v.get("name", ""):
                        cached_store = v
                        break

        # キャッシュヒット判定
        # URLが一致し、かつ以前の取得が「成功」している場合
        if pdf_url and cached_store:
            old_url = cached_store.get("pdf_url")
            old_status = cached_store.get("pricing", {}).get("status")
            
            if old_url == pdf_url and old_status == "success":
                print(f"  ✨ Cache Hit! PDF has not changed. Using existing data.", file=sys.stderr)
                # 既存データをそのまま使う
                pricing_data = cached_store["pricing"]
                
                # 結果出力して次へ
                result = {
                    "store_name": store['name'],
                    "pdf_url": pdf_url, 
                    "pricing": pricing_data
                }
                if not first: print(",", file=sys.stdout)
                print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stdout)
                sys.stdout.flush()
                first = False
                continue

        # キャッシュミス -> 実処理
        if pdf_url:
            print(f"  PDF Found: {pdf_url}", file=sys.stderr)
            pdf_bytes = download_pdf(pdf_url)
            
            if pdf_bytes:
                extracted = extract_prices_with_gemini(pdf_bytes)
                if extracted and extracted.get("weekday_30min"):
                    pricing_data = {
                        "status": "success",
                        "day": {
                            "30min": {"member": extracted["weekday_30min"], "general": None},
                            "free_time": {"member": extracted["weekday_free_time"], "general": None}
                        }
                    }
                    print(f"  ✅ Extracted: 30min={extracted['weekday_30min']}, Free={extracted['weekday_free_time']}", file=sys.stderr)
                else:
                    print("  ❌ Extraction failed or returned null.", file=sys.stderr)
        else:
            print("  ❌ PDF not found.", file=sys.stderr)

        result = {
            "store_name": store['name'],
            "pdf_url": pdf_url,
            "pricing": pricing_data
        }
        
        if not first: print(",", file=sys.stdout)
        print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stdout)
        sys.stdout.flush()
        first = False
        time.sleep(5) # レート制限対策

    print("]", file=sys.stdout)

if __name__ == "__main__":
    main()

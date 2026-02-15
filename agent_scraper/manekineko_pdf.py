import argparse
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
# .envファイルの読み込み
load_dotenv()

# Windows環境での文字化け対策 (UTF-8強制)
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def fetch_all_manekineko_stores():
    """stations_with_prices.jsonからまねきねこ全店舗を取得"""
    json_path = "data/stations_with_prices.json"
    stores_list = []
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for station, stores in data.get("stations", {}).items():
                    for s in stores:
                        if s.get("chain") == "manekineko":
                            stores_list.append({
                                "name": s.get("name"),
                                "url": s.get("url")
                            })
        except Exception as e:
            print(f"Error loading stores: {e}", file=sys.stderr)
    return stores_list

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
            im = page.to_image(resolution=150)
            target_image = im.original
            
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-2.0-flash-lite') # 軽量モデル指定
            
            # 思考プロセスを含めたプロンプト (強化版)
            prompt = """
            あなたはカラオケ料金の専門家です。この画像の料金表から、以下の条件に合う「数値」を正確に抽出してください。
            
            ## 必須条件
            1. **「一般（非会員）」と「会員」の料金を必ず両方探してください。**
            2. 表の中から「一般」または「非会員」の列と、「会員」または「アプリ会員」の列を明確に区別してください。
            3. もし「一般」の記載が全くない場合は、会員価格から勝手に計算せず、必ず null (取得不可) としてください。適当な推測は禁止です。
            4. 行（縦軸）は「昼（OPEN〜18:00頃）」の時間帯を見てください。
            5. 土日祝(Weekend)ではなく、**平日(Weekday)** の料金を優先してください。
            6. 「30分料金」と「フリータイム料金」の両方を抽出してください。

            ## 出力フォーマット (JSONのみ)
            ```json
            {
                "reasoning": "表の右側にある一般列を確認... 会員列と比較して...",
                "weekday_30min_general": 数値 または null,
                "weekday_30min_member": 数値 または null,
                "weekday_free_time_general": 数値 または null,
                "weekday_free_time_member": 数値 または null
            }
            ```
            ※数値が見つからない場合は null。文字（"円"など）は削除して数値のみにする。
            """

            max_retries = 3
            for attempt in range(max_retries):
                try:
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
                    if "429" in str(e) or "Resource exhausted" in str(e):
                        wait_time = (attempt + 1) * 20
                        print(f"  ⚠️ Quota exceeded. Retrying in {wait_time}s...", file=sys.stderr)
                        time.sleep(wait_time)
                    else:
                        raise e
            
            print("  ❌ Max retries exceeded.", file=sys.stderr)
            return None

    except Exception as e:
        print(f"Error in Gemini: {e}", file=sys.stderr)
        return None

def main():
    parser = argparse.ArgumentParser(description='Manekineko PDF Scraper')
    parser.add_argument('--force', action='store_true', help='Force re-download and re-analysis of all PDFs')
    parser.add_argument('--pdf-only', action='store_true', help='Only fetch PDF URLs, skip Gemini extraction')
    parser.add_argument('--output', type=str, help='Output JSON file path (optional)')
    args = parser.parse_args()

    # キャッシュデータの読み込み
    json_path = "data/stations_with_prices.json"
    cache_map = {}
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for station, stores in data.get("stations", {}).items():
                    for store in stores:
                        norm_name = store.get("name", "").replace(" ", "").replace("　", "")
                        cache_map[norm_name] = store
        except Exception as e:
            print(f"Warning: Failed to load cache: {e}", file=sys.stderr)

    # 全店舗リストの取得
    target_stores = fetch_all_manekineko_stores()
    if not target_stores:
        # フォールバック（既存のハードコードリスト）
        target_stores = [
            {"name": "カラオケまねきねこ 阪急東通り店", "url": "https://www.karaokemanekineko.jp/locations/osaka/osaka-shi/hankyu-higashidori-store/"},
            {"name": "カラオケまねきねこ 梅田芝田店", "url": "https://www.karaokemanekineko.jp/locations/osaka/osaka-shi/umeda-shibata-store/"},
            {"name": "カラオケまねきねこ 茶屋町店", "url": "https://www.karaokemanekineko.jp/locations/osaka/osaka-shi/chayamachi-store/"},
            {"name": "カラオケまねきねこ 阪急東通り2号店", "url": "https://www.karaokemanekineko.jp/locations/osaka/osaka-shi/hankyuhigashidori-2nd-store/"}
        ]

    results = []
    # 出力先の設定
    out_stream = sys.stdout
    if args.output:
        out_stream = open(args.output, 'w', encoding='utf-8')

    try:
        print("[", file=out_stream)
        first = True
        
        success_count = 0
        general_price_count = 0

        for store in target_stores:
            print(f"Processing {store['name']}...", file=sys.stderr)
            pdf_url = fetch_pdf_url(store['url'])
            
            pricing_data = {"status": "failed"}
            
            # キャッシュチェック (Forceモードならスキップ)
            norm_target = store['name'].replace(" ", "").replace("　", "")
            cached_store = cache_map.get(norm_target)
            
            # キャッシュヒット判定
            if not args.force and pdf_url and cached_store:
                old_url = cached_store.get("pdf_url")
                old_status = cached_store.get("pricing", {}).get("status")
                
                if old_url == pdf_url and old_status == "success":
                    print(f"  ✨ Cache Hit! PDF has not changed.", file=sys.stderr)
                    pricing_data = cached_store["pricing"]
                    
                    # 結果出力
                    result = {
                        "store_name": store['name'],
                        "pdf_url": pdf_url, 
                        "pricing": pricing_data
                    }
                    if not first: print(",", file=out_stream)
                    print(json.dumps(result, ensure_ascii=False, indent=2), file=out_stream)
                    if args.output: out_stream.flush()
                    else: sys.stdout.flush()
                    first = False
                    continue

            # 実処理
            if pdf_url:
                print(f"  PDF Found: {pdf_url}", file=sys.stderr)
                pdf_bytes = download_pdf(pdf_url)
                
                if pdf_bytes:
                    if args.pdf_only:
                        print("  Skipping Gemini extraction (--pdf-only)", file=sys.stderr)
                        extracted = None
                    else:
                        extracted = extract_prices_with_gemini(pdf_bytes)
                    if extracted and (extracted.get("weekday_30min_member") or extracted.get("weekday_30min_general")):
                        pricing_data = {
                            "status": "success",
                            "day": {
                                "30min": {
                                    "member": extracted.get("weekday_30min_member"), 
                                    "general": extracted.get("weekday_30min_general")
                                },
                                "free_time": {
                                    "member": extracted.get("weekday_free_time_member"), 
                                    "general": extracted.get("weekday_free_time_general")
                                }
                            }
                        }
                        print(f"  ✅ Extracted: 30min(Men/Gen)={extracted.get('weekday_30min_member')}/{extracted.get('weekday_30min_general')}", file=sys.stderr)
                        success_count += 1
                        if extracted.get("weekday_30min_general"):
                            general_price_count += 1
                    else:
                        print("  ❌ Extraction failed or returned null.", file=sys.stderr)
            else:
                print("  ❌ PDF not found.", file=sys.stderr)

            result = {
                "store_name": store['name'],
                "pdf_url": pdf_url,
                "pricing": pricing_data
            }
            
            if not first: print(",", file=out_stream)
            print(json.dumps(result, ensure_ascii=False, indent=2), file=out_stream)
            if args.output: out_stream.flush()
            else: sys.stdout.flush()
            first = False
            time.sleep(3) # レート制限対策

        print("]", file=out_stream)
        
    finally:
        if args.output and out_stream != sys.stdout:
            out_stream.close()

    print(f"\nExample Stats: Success={success_count}, WithGeneralPrice={general_price_count}", file=sys.stderr)

if __name__ == "__main__":
    main()

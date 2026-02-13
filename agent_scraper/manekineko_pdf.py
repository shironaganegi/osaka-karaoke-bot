"""
まねきねこPDF料金表スクレイピング
================================
公式サイトの店舗ページから料金表PDFを取得し、テキスト解析によって料金データを抽出する。

ターゲット: 大阪エリア（梅田・難波など）
"""

import requests
import pdfplumber
import re
import json
import io
import sys
import time
from pathlib import Path

# ターゲット店舗リスト (例: 梅田周辺)
TARGET_STORES = [
    {
        "name": "カラオケまねきねこ 阪急東通り店",
        "url": "https://www.karaokemanekineko.jp/locations/osaka/osaka-shi/hankyu-higashidori-store/"
    },
    {
        "name": "カラオケまねきねこ 阪急東通り2号店",
        "url": "https://www.karaokemanekineko.jp/locations/osaka/osaka-shi/hankyuhigashidori-2nd-store/"
    },
    {
         "name": "カラオケまねきねこ 千日前店",
         "url": "https://www.karaokemanekineko.jp/locations/osaka/osaka-shi/sennichimae-store/"
    }
]

def fetch_pdf_url(store_url):
    """店舗ページのHTMLからPDFリンクを抽出する"""
    try:
        response = requests.get(store_url, timeout=10)
        response.raise_for_status()
        html = response.text
        
        # 簡易的な正規表現で .pdf リンクを探す
        # href="/.../xxx.pdf" を抽出
        match = re.search(r'href="([^"]+\.pdf)"', html)
        if match:
            pdf_path = match.group(1)
            if pdf_path.startswith("http"):
                return pdf_path
            else:
                # 相対パスの場合はドメインを補完 (www.karaokemanekineko.jp を想定)
                return "https://www.karaokemanekineko.jp" + pdf_path
        return None
    except Exception as e:
        print(f"Error fetching HTML for {store_url}: {e}", file=sys.stderr)
        return None

def download_pdf(pdf_url):
    """PDFをメモリ上にダウンロードする"""
    try:
        response = requests.get(pdf_url, timeout=10)
        response.raise_for_status()
        return io.BytesIO(response.content)
    except Exception as e:
        print(f"Error downloading PDF {pdf_url}: {e}", file=sys.stderr)
        return None

def extract_prices_from_pdf(pdf_file):
    """
    PDFから料金を抽出する (高難易度)
    
    戦略:
    1. pdfplumberでテキストとテーブルを抽出
    2. キーワード「朝」「昼」「夜」や「30分」「フリータイム」の位置関係から数値を特定
    3. 数値っぽいものを正規表現で抽出
    """
    prices = {
        "day": {
            "30min": {"member": None, "general": None},
            "free_time": {"member": None, "general": None}
        },
        "status": "failed"
    }

    try:
        with pdfplumber.open(pdf_file) as pdf:
            if not pdf.pages:
                return prices

            page = pdf.pages[0] # 1ページ目を解析
            text = page.extract_text()
            
            # --- 画像PDF判定 ---
            if not text or len(text.strip()) < 10:
                print(f"  [Warning] Image-based PDF detected (text length: {len(text) if text else 0}). Cannot extract prices without OCR.", file=sys.stderr)
                # prices["status"] = "failed" # デフォルトのまま
                return prices

            tables = page.extract_tables()
            
            # デバッグ用: テキスト全表示
            # print("--- PDF TEXT ---")
            # print(text)
            # print("----------------")

            # テーブル解析アプローチ
            found_30min = False
            found_free = False

            for table in tables:
                for row in table:
                    # 行の内容を結合して文字列化
                    row_str = " ".join([str(cell) for cell in row if cell]).replace("\n", "")
                    
                    # 30分料金の行っぽいか？ (例: "30分", "OPEN〜18:00")
                    if "30分" in row_str and ("昼" in row_str or "OPEN" in row_str):
                        # 数値を抽出して、小さい方を会員、大きい方を一般と仮定
                        nums = [int(n) for n in re.findall(r'(\d+)', row_str) if int(n) > 10]
                        if len(nums) >= 2:
                            prices["day"]["30min"]["member"] = min(nums)
                            prices["day"]["30min"]["general"] = max(nums) # 簡易ロジック
                            found_30min = True

                    # フリータイムの行っぽいか？
                    if "フリータイム" in row_str and ("昼" in row_str or "OPEN" in row_str):
                         nums = [int(n) for n in re.findall(r'(\d+)', row_str) if int(n) > 500] # フリータイムは500円以上と仮定
                         if len(nums) >= 2:
                            prices["day"]["free_time"]["member"] = min(nums)
                            prices["day"]["free_time"]["general"] = max(nums)
                            found_free = True
            
            if found_30min or found_free:
                prices["status"] = "success"
            
    except Exception as e:
        print(f"Error parsing PDF: {e}", file=sys.stderr)

    return prices

def main():
    results = {}
    
    for store in TARGET_STORES:
        print(f"Processing {store['name']}...", file=sys.stderr)
        
        # 1. PDF URL取得
        pdf_url = fetch_pdf_url(store['url'])
        if not pdf_url:
            print(f"  PDF not found for {store['name']}", file=sys.stderr)
            continue
            
        print(f"  PDF URL: {pdf_url}", file=sys.stderr)
        
        # 2. PDFダウンロード
        pdf_file = download_pdf(pdf_url)
        if not pdf_file:
            continue
            
        # 3. 解析
        prices = extract_prices_from_pdf(pdf_file)
        print(f"  Extracted: {prices}", file=sys.stderr)
        
        # 4. 結果格納
        results[store['name']] = {
            "store_name": store['name'],
            "pdf_url": pdf_url,
            "pricing": prices
        }
        
        time.sleep(1) # サーバー負荷軽減

    # 結果出力 (JSON)
    print(json.dumps(list(results.values()), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()

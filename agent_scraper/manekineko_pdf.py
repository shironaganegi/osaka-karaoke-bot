"""
まねきねこPDF料金表スクレイピング (Gemini Vision Hybrid)
=====================================================
公式サイトの店舗ページから料金表PDFを取得し、テキスト解析または画像解析(Gemini)によって料金データを抽出する。

ターゲット: 大阪エリア（梅田・難波など）
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

# 外部ライブラリ (OCR/Vision用)
try:
    import google.generativeai as genai
except ImportError:
    print("Required libraries not found. Please install google-generativeai.", file=sys.stderr)
    sys.exit(1)

# ターゲット店舗リスト
TARGET_STORES = [
    {
        "name": "カラオケまねきねこ 阪急東通り店",
        "url": "https://www.karaokemanekineko.jp/locations/osaka/osaka-shi/hankyu-higashidori-store/"
    },
    # 他の店舗は省略可能
]

def fetch_pdf_url(store_url):
    """店舗ページのHTMLからPDFリンクを抽出する"""
    try:
        response = requests.get(store_url, timeout=10)
        response.raise_for_status()
        html = response.text
        
        match = re.search(r'href="([^"]+\.pdf)"', html)
        if match:
            pdf_path = match.group(1)
            if pdf_path.startswith("http"):
                return pdf_path
            else:
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
        return response.content # bytesを返す
    except Exception as e:
        print(f"Error downloading PDF {pdf_url}: {e}", file=sys.stderr)
        return None

def extract_prices_with_gemini(pdf_bytes):
    """
    画像PDF用: Gemini 1.5 Flash (Vision) を使って料金を抽出する
    """
def extract_prices_with_gemini(pdf_bytes):
    """
    画像PDF用: Gemini 1.5 Flash (Vision) を使って料金を抽出する
    """
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("Error: GOOGLE_API_KEY not found in environment variables.", file=sys.stderr)
        return None

    try:
        # 1. PDFを画像に変換 (1ページ目のみ) - pdfplumber (pypdfium2) を使用
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            if not pdf.pages: 
                return None
            
            # 解像度を指定して画像化 (デフォルト72dpiだと粗い可能性があるため150dpi程度に)
            im = pdf.pages[0].to_image(resolution=150)
            target_image = im.original # PIL Image object
        
        # 2. Gemini API設定
        genai.configure(api_key=api_key)
        
        # モデルリスト (優先度順)
        models_to_try = [
            'gemini-2.5-flash',
            'gemini-flash-latest',
            'gemini-pro-latest',
            'gemini-2.0-flash'
        ]
        
        # 3. プロンプト作成
        prompt = """
        このカラオケ料金表の画像から、『一般会員(Member Price)』の『平日・昼（OPEN〜18:00等）』 の料金を抽出してください。
        
        条件:
        - 会員価格(Member)を最優先してください。一般価格(General)ではありません。
        - 30分料金(30min)とフリータイム(Free Time)の数値を抽出してください。
        - フリータイムがない場合は null にしてください。
        - ワンドリンクオーダー制などの条件は無視し、室料（またはパック料金）の数値を抽出してください。
        - 学生料金ではなく、通常の会員料金を抽出してください。
        
        以下のJSON形式のみを返してください。Markdownのコードブロック(```json ... ```)を含めないでください。
        
        {
            "weekday_30min": 数値,
            "weekday_free_time": 数値 または null
        }
        """

        response = None
        for model_name in models_to_try:
            try:
                print(f"  Sending image to Gemini Vision API ({model_name})...", file=sys.stderr)
                model = genai.GenerativeModel(model_name)
                response = model.generate_content([prompt, target_image])
                break # 成功したらループを抜ける
            except Exception as e:
                print(f"  [Warning] Failed with {model_name}: {e}", file=sys.stderr)
                continue
        
        if not response:
             print("  [Error] All Gemini models failed.", file=sys.stderr)
             return None

        response_text = response.text.strip()
        
        # Markdown削除 (念のため)
        response_text = response_text.replace("```json", "").replace("```", "")
        
        data = json.loads(response_text)
        return data

    except Exception as e:
        print(f"Error in Gemini Vision processing: {e}", file=sys.stderr)
        return None

def extract_prices_from_pdf(pdf_bytes):
    """
    ハイブリッド抽出ロジック
    """
    prices = {
        "day": {
            "30min": {"member": None, "general": None},
            "free_time": {"member": None, "general": None}
        },
        "status": "failed"
    }

    # step 1: pdfplumber (Text Extraction)
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            if pdf.pages:
                page = pdf.pages[0]
                text = page.extract_text()
                
                # テキストが十分に取れない場合は画像PDFとみなす
                if not text or len(text.strip()) < 50:
                    print("  [Info] Image-based PDF detected. Switching to Gemini Vision.", file=sys.stderr)
                    gemini_result = extract_prices_with_gemini(pdf_bytes)
                    if gemini_result:
                         # Geminiの結果を統合
                         prices["day"]["30min"]["member"] = gemini_result.get("weekday_30min")
                         prices["day"]["free_time"]["member"] = gemini_result.get("weekday_free_time")
                         prices["status"] = "success"
                         return prices
                    else:
                        return prices # status failed
                
                # テキストがある場合は従来のロジック (省略 - 今回は画像PDFターゲット)
                # ... (既存のロジックを入れる場所だが、今回はGeminiテスト優先のため省略または簡易実装)
                pass

    except Exception as e:
        print(f"Error parsing PDF: {e}", file=sys.stderr)

    return prices

def main():
    results = {}
    
    for store in TARGET_STORES:
        print(f"Processing {store['name']}...", file=sys.stderr)
        
        pdf_url = fetch_pdf_url(store['url'])
        if not pdf_url:
            print(f"  PDF not found for {store['name']}", file=sys.stderr)
            continue
            
        print(f"  PDF URL: {pdf_url}", file=sys.stderr)
        
        pdf_bytes = download_pdf(pdf_url)
        if not pdf_bytes:
            continue
            
        prices = extract_prices_from_pdf(pdf_bytes)
        print(f"  Extracted: {json.dumps(prices, ensure_ascii=False)}", file=sys.stderr)
        
        results[store['name']] = {
            "store_name": store['name'],
            "pdf_url": pdf_url,
            "pricing": prices
        }
        
        time.sleep(1)

    print(json.dumps(list(results.values()), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()

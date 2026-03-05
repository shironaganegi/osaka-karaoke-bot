import requests
import pdfplumber
import io
import sys
import os
import json
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

def extract_prices_debug():
    url = "https://www.karaokemanekineko.jp/locations/osaka/osaka-shi/umeda-shibata-store/"
    pdf_url = "https://d1k5d0nneloh3k.cloudfront.net/wp-content/uploads/2025/11/28132223/448-7.pdf" # Example PDF (Umeda Shibata?) Or just try the first one from results

    print(f"Downloading {pdf_url}...")
    try:
        response = requests.get(pdf_url, timeout=15)
        response.raise_for_status()
        pdf_bytes = response.content
    except Exception as e:
        print(f"Download failed: {e}")
        return

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("API Key missing")
        return

    print("Analyzing with Gemini...")
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            page = pdf.pages[0]
            im = page.to_image(resolution=150)
            target_image = im.original
            
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-2.0-flash-lite')
            
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
            """

            response = model.generate_content([prompt, target_image])
            print(f"Response:\n{response.text}")

    except Exception as e:
        print(f"Gemini Error: {e}")

if __name__ == "__main__":
    extract_prices_debug()

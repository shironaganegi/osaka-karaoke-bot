import os
import sys
import io
import requests
import pytesseract
import fitz  # PyMuPDF
from PIL import Image
import google.generativeai as genai
from dotenv import load_dotenv
import json

# Load Env
load_dotenv()

# Configuration
TESSERACT_CMD = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
TESSDATA_DIR = os.path.abspath('data/tessdata')
API_KEY = os.environ.get("GOOGLE_API_KEY")

# Setup Tesseract
pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
os.environ['TESSDATA_PREFIX'] = TESSDATA_DIR

# Setup Gemini
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash-lite')

# Windows stdout encoding fix
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def fetch_pdf_bytes(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.content
    except Exception as e:
        print(f"Error downloading PDF: {e}")
    return None

def ocr_pdf_to_text(pdf_bytes):
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        if len(doc) == 0: return ""
        page = doc[0]
        pix = page.get_pixmap(dpi=300)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        text = pytesseract.image_to_string(img, lang='jpn+eng', config='--psm 6')
        return text
    except Exception as e:
        print(f"OCR Error: {e}")
        return ""

def analyze_text_debug(text):
    prompt = """
    あなたはカラオケ料金表の解析エキスパートです。
    以下のOCRテキストから、「平日・昼（12:00〜18:00頃）」の「30分料金」と「フリータイム料金」を特定してください。
    
    特に、「朝うた（〜12:00、〜11:00など）」と「昼料金」を明確に区別してください。
    
    テキスト全体を分析し、以下の情報をJSONで返してください：
    {
        "raw_text_excerpt": "価格周辺のテキスト抜粋",
        "morning_price_found": "朝うたの価格があれば記載",
        "daytime_price_found": "昼料金（一般・会員）",
        "free_time_price_found": "昼フリータイム（一般・会員）",
        "reasoning": "なぜその価格を選んだかの理由"
    }
    """
    try:
        response = model.generate_content([prompt, text])
        print("\n--- GEMINI AI ANALYSIS ---")
        print(response.text)
        return response.text
    except Exception as e:
        print(f"AI Error: {e}")
        return None

def main():
    url = "https://d1k5d0nneloh3k.cloudfront.net/wp-content/uploads/2025/11/28132223/448-7.pdf" # Namba HIPS URL
    print(f"Fetch: {url}")
    
    pdf_bytes = fetch_pdf_bytes(url)
    if not pdf_bytes: return

    print("Running OCR...")
    text = ocr_pdf_to_text(pdf_bytes)
    
    with open("namba_hips_ocr.txt", "w", encoding="utf-8") as f:
        f.write(text)
    print("Saved OCR text to namba_hips_ocr.txt")

    print("\n--- OCR TEXT OUTPUT ---")
    print(text)
    print("-----------------------")

    # Retry loop for AI
    import time
    max_retries = 3
    for i in range(max_retries):
        try:
            analyze_text_debug(text)
            break
        except Exception as e:
            if "429" in str(e):
                print(f"Rate limit 429. Retrying in 20s... ({i+1}/{max_retries})")
                time.sleep(20)
            else:
                print(f"AI Error: {e}")
                break

if __name__ == "__main__":
    main()

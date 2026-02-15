
import requests
import fitz # PyMuPDF
import pytesseract
from PIL import Image
import io
import sys
import re

import os

# Tesseract Setup
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
# Set TESSDATA_PREFIX to local folder
os.environ['TESSDATA_PREFIX'] = os.path.join(os.getcwd(), 'tessdata')

def fetch_pdf_bytes(pdf_url):
    try:
        response = requests.get(pdf_url, timeout=10)
        response.raise_for_status()
        return response.content
    except Exception as e:
        print(f"PDF Download Error: {e}")
        return None

# ... (imports)
import google.generativeai as genai
import json
import sys

# Ensure root is in path to import shared.config
sys.path.append(os.getcwd())
try:
    from shared.config import API_KEY
except ImportError:
    API_KEY = os.environ.get("GEMINI_API_KEY")

model = None
if API_KEY:
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel('gemini-2.0-flash-lite')

def get_pdf_first_page_image(pdf_bytes):
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        if len(doc) == 0: return None
        page = doc[0]
        pix = page.get_pixmap(dpi=300)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        return img
    except Exception as e:
        print(f"Image Error: {e}")
        return None

def analyze_image_with_ai(img):
    if not model:
        print("No API Key")
        return None
        
    prompt = """
    あなたはカラオケ料金のデータ抽出AIです。
    提供された料金表の画像から、「平日・昼（OPEN〜18:00頃）」の「30分料金」を抽出してください。
    ... (same prompt as main script) ...
    """
    try:
        response = model.generate_content([prompt, img])
        print("--- AI Raw Response ---")
        print(response.text)
        print("-----------------------")
        return json.loads(response.text.replace("```json", "").replace("```", "").strip())
    except Exception as e:
        print(f"AI Error: {e}")
        return None

target_url = "https://d1k5d0nneloh3k.cloudfront.net/wp-content/uploads/2025/11/28132640/767-8.pdf"
print(f"Downloading {target_url}...")
pdf_bytes = fetch_pdf_bytes(target_url)

if pdf_bytes:
    print("Converting to Image...")
    img = get_pdf_first_page_image(pdf_bytes)
    if img:
        print("Analyzing with Vision...")
        data = analyze_image_with_ai(img)
        print(f"Result: {data}")
    else:
        print("Failed to get image")


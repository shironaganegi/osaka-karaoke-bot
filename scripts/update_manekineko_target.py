import json
import os
import sys
import io
import time
import requests
import pytesseract
import fitz  # PyMuPDF
from PIL import Image
import google.generativeai as genai
from datetime import datetime
from dotenv import load_dotenv

# Load Env
load_dotenv()

# Configuration
TESSERACT_CMD = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
TESSDATA_DIR = os.path.abspath('data/tessdata')
JSON_PATH = "data/stations_with_prices.json"
API_KEY = os.environ.get("GOOGLE_API_KEY")

# Setup Tesseract
pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
os.environ['TESSDATA_PREFIX'] = TESSDATA_DIR

# Setup Gemini
if not API_KEY:
    print("Error: GOOGLE_API_KEY not found.", file=sys.stderr)
    sys.exit(1)
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

TARGET_STORES = [
    "カラオケまねきねこ 千日前2号店",
    "カラオケまねきねこ 南海通り2号店",
    "カラオケまねきねこ 南海通り店"
]

def fetch_pdf_bytes(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.content
    except Exception as e:
        print(f"  Error downloading PDF: {e}", file=sys.stderr)
    return None

def get_pdf_first_page_image(pdf_bytes):
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        if len(doc) == 0: return None
        page = doc[0]
        pix = page.get_pixmap(dpi=300)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        return img
    except Exception as e:
        print(f"  Image Extraction Error: {e}", file=sys.stderr)
        return None

def analyze_image_with_ai(img):
    prompt = """
    あなたはカラオケ料金のデータ抽出AIです。
    提供された料金表の画像から、「平日・昼（OPEN〜18:00頃）」の「30分料金」を抽出してください。
    
    ## 抽出ルール (絶対遵守)
    1. **ターゲット**: 「一般（非会員）」と「会員（アプリ会員/LINE会員など）」の両方の価格。
    2. **除外**: 「朝うた」「ゼロカラ」「深夜料金」「シニア割引」「高校生室料0円」などは無視してください。
    3. **検証**: 価格は通常 **100円〜600円** の範囲内です。特に安価（100円〜150円）な場合も、それが「学生限定」や「朝うた」でなければ正当な価格として抽出してください。
    4. **フリータイム**: もし記載があれば「平日昼フリータイム」の価格も抽出してください。

    ## 出力フォーマット (JSONのみ)
    ```json
    {
        "weekday_30min_general": 数値 または null,
        "weekday_30min_member": 数値 または null,
        "weekday_free_member": 数値 または null,
        "weekday_free_general": 数値 または null,
        "reasoning": "画像のどこを見て判断したか"
    }
    ```
    """
    
    try:
        response = model.generate_content([prompt, img])
        raw_json = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw_json)
        return data
    except Exception as e:
        print(f"  AI Error: {e}", file=sys.stderr)
        if "429" in str(e): raise e
        return None

def validate_price(price):
    if price is None: return False
    if not isinstance(price, (int, float)): return False
    return 120 <= price <= 600

def main():
    if not os.path.exists(JSON_PATH):
        print("Error: JSON file not found.", file=sys.stderr)
        return

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    updated_count = 0
    stations = data.get("stations", {})
    
    print("Starting Targeted Price Update (Force Vision)...", file=sys.stderr)

    for station_name, stores in stations.items():
        for store in stores:
            if store.get("name") not in TARGET_STORES: continue
            
            pdf_url = store.get("pdf_url")
            if not pdf_url: 
                print(f"Skip {store['name']}: No PDF URL", file=sys.stderr)
                continue

            print(f"Processing {store['name']}...", file=sys.stderr)
            
            pdf_bytes = fetch_pdf_bytes(pdf_url)
            if not pdf_bytes: continue

            img = get_pdf_first_page_image(pdf_bytes)
            if not img: continue
            
            mem_30 = None
            gen_30 = None
            mem_free = None
            gen_free = None
            source = "None"
            
            # Force Gemini Vision
            try:
                ai_data = analyze_image_with_ai(img)
                if ai_data:
                    mem_30 = ai_data.get("weekday_30min_member")
                    gen_30 = ai_data.get("weekday_30min_general")
                    mem_free = ai_data.get("weekday_free_member")
                    gen_free = ai_data.get("weekday_free_general")
                    
                    if validate_price(mem_30) or validate_price(gen_30):
                        source = "GeminiVision"
                        print(f"  Gemini Vision Result: Mem={mem_30}, Gen={gen_30}, FreeMem={mem_free}", file=sys.stderr)
            except Exception as e:
                print(f"  Gemini Vision Failed: {e}", file=sys.stderr)
                if "429" in str(e):
                        print("  ⚠️ API Rate Limit 429. Waiting 30s...", file=sys.stderr)
                        time.sleep(30)

            is_valid = False
            if (validate_price(mem_30) or validate_price(gen_30)):
                is_valid = True
            
            if is_valid:
                if "pricing" not in store: store["pricing"] = {}
                store["pricing"]["status"] = "success"
                store["pricing"]["scraped_at"] = datetime.now().isoformat()
                
                if "day" not in store["pricing"]: store["pricing"]["day"] = {}
                
                # 30min
                store["pricing"]["day"]["30min"] = {}
                if mem_30: store["pricing"]["day"]["30min"]["member"] = int(mem_30)
                if gen_30: store["pricing"]["day"]["30min"]["general"] = int(gen_30)
                
                # Free Time
                store["pricing"]["day"]["free_time"] = {}
                if mem_free: store["pricing"]["day"]["free_time"]["member"] = int(mem_free)
                elif mem_30: store["pricing"]["day"]["free_time"]["member"] = int(mem_30) * 4 # Fallback
                
                if gen_free: store["pricing"]["day"]["free_time"]["general"] = int(gen_free)
                elif gen_30: store["pricing"]["day"]["free_time"]["general"] = int(gen_30) * 4 # Fallback

                updated_count += 1
                print(f"  -> Updated JSON using {source}", file=sys.stderr)
            else:
                print("  -> Skipped: No valid prices found via Vision.", file=sys.stderr)

            time.sleep(1) 

    if updated_count > 0:
        with open(JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"\nSuccessfully updated {updated_count} stores.")
    else:
        print("\nNo stores updated.", file=sys.stderr)

if __name__ == "__main__":
    main()

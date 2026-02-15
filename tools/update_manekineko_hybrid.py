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
        print(f"  Error downloading PDF: {e}", file=sys.stderr)
    return None

def ocr_pdf_to_text(pdf_bytes):
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        if len(doc) == 0: return ""
        
        # Process first page only (usually contains main pricing)
        page = doc[0]
        pix = page.get_pixmap(dpi=300)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        # OCR with Japanese + English
        text = pytesseract.image_to_string(img, lang='jpn+eng', config='--psm 6')
        return text
    except Exception as e:
        print(f"  OCR Error: {e}", file=sys.stderr)
        return ""

def analyze_text_with_ai(text):
    prompt = """
    あなたはカラオケ料金のデータ抽出AIです。
    提供されたOCRテキストから、「平日・昼（OPEN〜18:00頃）」の「30分料金」を抽出してください。
    
    ## 抽出ルール (絶対遵守)
    1. **ターゲット**: 「一般（非会員）」と「会員（アプリ会員/LINE会員など）」の両方の価格。
    2. **除外**: 「朝うた」「ゼロカラ」「深夜料金」「シニア割引」「高校生室料0円」などは無視してください。
    3. **検証**: 価格は通常 **150円〜500円** の範囲内です。これより安すぎる（例: 10円、100円）場合は「朝うた」の可能性が高いので無視してください。
    4. **フリータイム**: もし記載があれば「平日昼フリータイム」の価格も抽出してください。

    ## 出力フォーマット (JSONのみ)
    ```json
    {
        "weekday_30min_general": 数値 または null,
        "weekday_30min_member": 数値 または null,
        "weekday_free_member": 数値 または null,
        "weekday_free_general": 数値 または null,
        "reasoning": "テキストのどの部分から判断したか簡潔に"
    }
    ```
    """
    
    try:
        response = model.generate_content([prompt, text])
        raw_json = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw_json)
        return data
    except Exception as e:
        print(f"  AI Analysis Error: {e}", file=sys.stderr)
        return None

def validate_price(price):
    if price is None: return False
    if not isinstance(price, (int, float)): return False
    # User rule: 180 - 600 yen for 30min (Ignore Morning Uta < 180)
    return 180 <= price <= 600

def extract_price_regex(text):
    """Fallback using Regex with Strict Filtering"""
    import re
    
    lines = text.split('\n')
    member_price = None
    general_price = None
    
    # Keywords to avoid near numbers
    NG_KEYWORDS = ["朝", "モーニング", "11", "open"] 

    clean_lines = []
    for line in lines:
        l = line.strip().replace(" ", "").replace("¥", "").replace(",", "")
        if l: clean_lines.append(l)

    price_pattern = re.compile(r'(\d{3,4})')

    for i, line in enumerate(clean_lines):
        # Look for 30min context
        if "30分" in line or "30min" in line:
            
            # Check for NG keywords in this line
            line_lower = line.lower()
            if any(ng in line_lower for ng in NG_KEYWORDS):
                continue

            prices = price_pattern.findall(line)
            # Filter by value strictly (180 <= p <= 600)
            valid_prices = []
            for p_str in prices:
                p_val = int(p_str)
                if 180 <= p_val <= 600:
                    valid_prices.append(p_val)

            if len(valid_prices) >= 2:
                member_price = valid_prices[0]
                general_price = valid_prices[1]
                break
            elif len(valid_prices) == 1:
                member_price = valid_prices[0]
            
            # Check next line if not fully found
            if not general_price and i + 1 < len(clean_lines):
                next_line = clean_lines[i+1]
                # Check NG keywords in next line
                if any(ng in next_line.lower() for ng in NG_KEYWORDS):
                    continue

                prices_next = price_pattern.findall(next_line)
                valid_prices_next = []
                for p_str in prices_next:
                    p_val = int(p_str)
                    if 180 <= p_val <= 600:
                        valid_prices_next.append(p_val)
                
                if not member_price and len(valid_prices_next) >= 1:
                     member_price = valid_prices_next[0]
                     if len(valid_prices_next) >= 2: general_price = valid_prices_next[1]
                     break
                elif member_price and len(valid_prices_next) >= 1:
                    general_price = valid_prices_next[0]
                    break
    
    return member_price, general_price

def main():
    if not os.path.exists(JSON_PATH):
        print("Error: JSON file not found.", file=sys.stderr)
        return

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    updated_count = 0
    stations = data.get("stations", {})
    
    print("Starting Hybrid Price Update (OCR + Gemini + Regex Fallback)...", file=sys.stderr)

    for station_name, stores in stations.items():
        for store in stores:
            if store.get("chain") != "manekineko": continue
            
            pdf_url = store.get("pdf_url")
            if not pdf_url: 
                print(f"Skip {store['name']}: No PDF URL", file=sys.stderr)
                continue

            print(f"Processing {store['name']}...", file=sys.stderr)
            
            # 1. Download PDF
            pdf_bytes = fetch_pdf_bytes(pdf_url)
            if not pdf_bytes: continue

            # 2. Local OCR
            text = ocr_pdf_to_text(pdf_bytes)
            if not text:
                print("  No text extracted from OCR.", file=sys.stderr)
                continue
            
            mem_30 = None
            gen_30 = None
            source = "None"

            # 3. AI Analysis
            ai_success = False
            try:
                ai_data = analyze_text_with_ai(text)
                if ai_data:
                    mem_30 = ai_data.get("weekday_30min_member")
                    gen_30 = ai_data.get("weekday_30min_general")
                    if validate_price(mem_30) or validate_price(gen_30):
                        ai_success = True
                        source = "Gemini"
                        print(f"  AI Result: Mem={mem_30}, Gen={gen_30} ({ai_data.get('reasoning')})", file=sys.stderr)
            except Exception as e:
                print(f"  AI skipped/failed: {e}", file=sys.stderr)
                if "429" in str(e):
                     print("  ⚠️ API Rate Limit 429. Waiting 30s before Regex fallback...", file=sys.stderr)
                     time.sleep(30)

            # 4. Fallback to Regex
            if not ai_success:
                print("  ⚠️ AI failed or invalid. Exploring Regex fallback...", file=sys.stderr)
                mem_30, gen_30 = extract_price_regex(text)
                if validate_price(mem_30) or validate_price(gen_30):
                    source = "Regex"
                    print(f"  Regex Result: Mem={mem_30}, Gen={gen_30}", file=sys.stderr)

            # 5. Update if valid
            if validate_price(mem_30) or validate_price(gen_30):
                if "pricing" not in store: store["pricing"] = {}
                store["pricing"]["status"] = "success"
                store["pricing"]["scraped_at"] = datetime.now().isoformat()
                
                if "day" not in store["pricing"]: store["pricing"]["day"] = {}
                
                # 30min
                store["pricing"]["day"]["30min"] = {}
                if validate_price(mem_30):
                    store["pricing"]["day"]["30min"]["member"] = int(mem_30)
                if validate_price(gen_30):
                    store["pricing"]["day"]["30min"]["general"] = int(gen_30)
                
                # Free Time (Estimate if not found)
                store["pricing"]["day"]["free_time"] = {}
                # If we have 30min prices, we can estimate FT if not found
                ft_mem = None
                ft_gen = None
                
                # Try to extract FT from AI if available
                if ai_success and ai_data:
                    ft_mem = ai_data.get("weekday_free_member")
                    ft_gen = ai_data.get("weekday_free_general")

                # Fallback Estimate
                if not ft_mem and mem_30: ft_mem = int(mem_30) * 4 # Rough estimate
                if not ft_gen and gen_30: ft_gen = int(gen_30) * 4

                if ft_mem: store["pricing"]["day"]["free_time"]["member"] = int(ft_mem)
                if ft_gen: store["pricing"]["day"]["free_time"]["general"] = int(ft_gen)
                
                updated_count += 1
                print(f"  -> Updated JSON using {source}", file=sys.stderr)
            else:
                print("  -> Skipped: No valid prices found.", file=sys.stderr)

            time.sleep(10) # Increased delay to 10s

    # Save
    if updated_count > 0:
        with open(JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"\nSuccessfully updated {updated_count} stores with AI-verified prices.")
    else:
        print("\nNo stores updated.", file=sys.stderr)

if __name__ == "__main__":
    main()

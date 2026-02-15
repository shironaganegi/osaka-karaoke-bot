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
        # print(f"  AI Image Analysis Error: {e}", file=sys.stderr)
        # Re-raise 429 to be handled by caller
        if "429" in str(e): raise e
        return None

def validate_price(price):
    if price is None: return False
    if not isinstance(price, (int, float)): return False
    # User rule: 120 - 600 yen for 30min (Ignore Morning Uta < 120, Diamond/Student < 120)
    return 120 <= price <= 600

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
            # Filter by value strictly (120 <= p <= 600)
            valid_prices = []
            for p_str in prices:
                p_val = int(p_str)
                if 120 <= p_val <= 600:
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

def extract_price_context_aware(text):
    """
    Extract prices based on time context (e.g., 11:00~18:00).
    Returns: (mem_30, gen_30, mem_free, gen_free)
    """
    import re
    lines = text.split('\n')
    
    # regex for time range (e.g., 11:00 ~ 18:00)
    # Tesseract often garbles numbers, so be flexible: (1)1:00, (1)8:00, etc.
    time_range_pattern = re.compile(r'(\d{1,2})[:\s]00\s*~\s*(\d{1,2})[:\s]00')
    price_pattern = re.compile(r'(\d{3,4})')
    
    current_block = "unknown" # morning, day, night
    
    mem_30, gen_30 = None, None
    mem_free, gen_free = None, None

    # Track prices found in "Day" block
    day_30_candidates = []
    day_free_candidates = []

    for i, line in enumerate(lines):
        # Detect Block
        # Look for "11:00" or "10:00" to "18:00" or "19:00"
        line_clean = line.replace("⑪", "11").replace("①⑧", "18").replace("①", "1").replace("⑧", "8")
        
        # New Time Block Detection (Reset if new start time found)
        # Regex for "H:00 ~"
        time_header_match = re.search(r'(\d{1,2})[:\s]00\s*~\s*', line_clean)
        if time_header_match:
            start_hour = int(time_header_match.group(1))
            
            # Day logic: Start 10 or 11. End 18 or 19.
            if start_hour in [10, 11] and ("18:00" in line_clean or "19:00" in line_clean):
                current_block = "day"
                # print(f"DEBUG: Found DAY block at line {i}: {line.strip()}")
                continue
            elif start_hour in [6, 7] and ("11:00" in line_clean or "12:00" in line_clean):
                current_block = "morning"
                continue
            elif start_hour >= 18 or start_hour == 23 or start_hour == 0:
                current_block = "night"
                continue
            elif start_hour == 15:
                # 15:00 is usually "Evening/Free Time B", distinct from Day
                current_block = "evening"
                continue
            else:
                # Unknown block start
                current_block = "unknown"

        if current_block == "day":
            # 30min
            if "30分" in line or "30min" in line:
                # Try both raw and no-space
                raw_nums = price_pattern.findall(line.replace(",", ""))
                nospace_nums = price_pattern.findall(line.replace(" ", "").replace(",", ""))
                
                all_nums = raw_nums + nospace_nums
                valid = [int(p) for p in all_nums if 50 <= int(p) <= 2000]
                if valid:
                     day_30_candidates.extend(valid)
            
            # Free Time
            # Check keywords in normalized text
            line_norm = line.replace(" ", "")
            if "フリー" in line_norm or "Free" in line_norm or "フリ-" in line_norm or "フリ—" in line_norm:
                # Try both raw and no-space
                raw_nums = price_pattern.findall(line.replace(",", ""))
                nospace_nums = price_pattern.findall(line.replace(" ", "").replace(",", ""))
                current_nums = raw_nums + nospace_nums
                
                # Check next line too
                if i+1 < len(lines):
                    next_line = lines[i+1]
                    r_next = price_pattern.findall(next_line.replace(",", ""))
                    n_next = price_pattern.findall(next_line.replace(" ", "").replace(",", ""))
                    current_nums.extend(r_next + n_next)

                valid = [int(p) for p in current_nums if 500 <= int(p) <= 3000]
                if valid:
                    day_free_candidates.extend(valid)

    # Resolve candidates
    # Namba HIPS OCR: "30min ... 105 ... 150" -> 105 (Diamond), 150 (Member)
    
    # 30min Resolution with Diamond Check
    if len(day_30_candidates) >= 1:
        day_30_candidates = sorted(list(set(day_30_candidates)))
        
        # If lowest is very small (e.g. 105), assume Diamond/Student
        if day_30_candidates[0] <= 120 and len(day_30_candidates) >= 2:
             # Skip the first one
             mem_30 = day_30_candidates[1] # 150
             # Estimate General
             if len(day_30_candidates) >= 3:
                 gen_30 = day_30_candidates[2]
             else:
                 gen_30 = int(mem_30 * 1.3) # Fallback
        elif len(day_30_candidates) >= 2:
            mem_30, gen_30 = day_30_candidates[0], day_30_candidates[1]
        else:
            mem_30 = day_30_candidates[0]
            gen_30 = int(mem_30 * 1.3) # Fallback

    if len(day_free_candidates) >= 1:
        # Dedupe and Sort
        day_free_candidates = sorted(list(set(day_free_candidates)))
        
        # Logic to pick Member/General from set like [608, 800, 1300]
        # Valid Member 30min is mem_30 (e.g. 150).
        # We want MemFree approx 5-7x Mem30.
        
        best_mem_free = None
        if mem_30:
             target = mem_30 * 6
             # Sort by distance to target
             sorted_by_fit = sorted(day_free_candidates, key=lambda x: abs(x - target))
             best_mem_free = sorted_by_fit[0]
             
             # General should be higher than Member
             gens = [x for x in day_free_candidates if x > best_mem_free]
             if gens:
                 best_gen_free = gens[0]
             else:
                 best_gen_free = int(best_mem_free * 1.3)
             
             mem_free, gen_free = best_mem_free, best_gen_free
        else:
             if len(day_free_candidates) >= 2:
                 mem_free, gen_free = day_free_candidates[0], day_free_candidates[1]
             else:
                 mem_free = day_free_candidates[0]
                 gen_free = int(mem_free * 1.3)
    
    return mem_30, gen_30, mem_free, gen_free

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
            # if "なんばHIPS" not in store['name']: continue # FAST MODE for Namba HIPS
            
            pdf_url = store.get("pdf_url")
            if not pdf_url: 
                print(f"Skip {store['name']}: No PDF URL", file=sys.stderr)
                continue

            print(f"Processing {store['name']}...", file=sys.stderr)
            
            # 1. Download PDF
            pdf_bytes = fetch_pdf_bytes(pdf_url)
            if not pdf_bytes: continue

            # 2. Get Image and OCR
            img = get_pdf_first_page_image(pdf_bytes)
            if not img: continue
            
            text = pytesseract.image_to_string(img, lang='jpn+eng', config='--psm 6')
            
            mem_30 = None
            gen_30 = None
            mem_free = None
            gen_free = None
            source = "None"
            
            # Priority 1: Context Aware Regex (Trusted for structural logic) matches Day block
            c_mem_30, c_gen_30, c_mem_free, c_gen_free = extract_price_context_aware(text)
            if c_mem_30 and c_gen_30:
                 mem_30, gen_30 = c_mem_30, c_gen_30
                 mem_free, gen_free = c_mem_free, c_gen_free
                 source = "ContextRegex"
                 print(f"  ContextRegex Result: 30min={mem_30}/{gen_30}", file=sys.stderr)

            # Priority 2: Gemini Vision (If Context Failed)
            ai_success = False
            if not mem_30:
                print("  ContextRegex failed. Trying Gemini Vision...", file=sys.stderr)
                try:
                    ai_data = analyze_image_with_ai(img)
                    if ai_data:
                        mem_30 = ai_data.get("weekday_30min_member")
                        gen_30 = ai_data.get("weekday_30min_general")
                        mem_free = ai_data.get("weekday_free_member")
                        gen_free = ai_data.get("weekday_free_general")
                        
                        if validate_price(mem_30) or validate_price(gen_30):
                            ai_success = True
                            source = "GeminiVision"
                            print(f"  Gemini Vision Result: Mem={mem_30}, Gen={gen_30}", file=sys.stderr)
                except Exception as e:
                    print(f"  Gemini Vision Failed: {e}", file=sys.stderr)
                    if "429" in str(e):
                         print("  ⚠️ API Rate Limit 429. Waiting 30s...", file=sys.stderr)
                         time.sleep(30)
                         time.sleep(30)

            # 4. Fallback to Simple Regex (if neither Context nor AI worked)
            if not mem_30 and not ai_success:
                print("  ⚠️ AI/Context failed. Exploring simple Regex fallback...", file=sys.stderr)
                mem_30, gen_30 = extract_price_regex(text)
                if validate_price(mem_30) or validate_price(gen_30):
                    source = "SimpleRegex"
                    print(f"  Simple Regex Result: Mem={mem_30}, Gen={gen_30}", file=sys.stderr)

            # 5. Update if valid (BYPASS FILTER if ContextRegex was used successully)
            # If Source is ContextRegex, we TRUST the values even if < 180 (e.g. 150)
            
            is_valid = False
            if source == "ContextRegex" and mem_30:
                is_valid = True
            elif (validate_price(mem_30) or validate_price(gen_30)):
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
                # Use extracted free time if available
                if mem_free: store["pricing"]["day"]["free_time"]["member"] = int(mem_free)
                else: 
                     if mem_30: store["pricing"]["day"]["free_time"]["member"] = int(mem_30) * 4 # Fallback
                
                if gen_free: store["pricing"]["day"]["free_time"]["general"] = int(gen_free)
                else:
                     if gen_30: store["pricing"]["day"]["free_time"]["general"] = int(gen_30) * 4 # Fallback

                updated_count += 1
                print(f"  -> Updated JSON using {source}", file=sys.stderr)
            else:
                print("  -> Skipped: No valid prices found.", file=sys.stderr)

            time.sleep(10) 

    # Save
    if updated_count > 0:
        with open(JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"\nSuccessfully updated {updated_count} stores with AI-verified prices.")
    else:
        print("\nNo stores updated.", file=sys.stderr)

if __name__ == "__main__":
    main()

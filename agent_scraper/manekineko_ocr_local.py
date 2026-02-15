import json
import time
import os
import io
import sys
import re
import requests
import pytesseract
import fitz  # PyMuPDF
from PIL import Image

# Windows stdout encoding fix
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Configuration
TESSERACT_CMD = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
TESSDATA_DIR = os.path.abspath('data/tessdata')

# Set Tesseract Path
pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

# Env var for data
os.environ['TESSDATA_PREFIX'] = TESSDATA_DIR

def fetch_pdf_bytes(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            return response.content
        return None
    except Exception as e:
        print(f"  Error downloading PDF: {e}", file=sys.stderr)
        return None

def extract_price_from_text(text):
    """
    Extract 30min prices for Member and General from OCR text.
    Heuristic: Look for "30分" line, then find prices.
    Manekineko tables usually:
    [Time] [Member] [General]
    [30分] [100] [200]
    """
    lines = text.split('\n')
    member_price = None
    general_price = None

    # Cleaning
    clean_lines = []
    for line in lines:
        l = line.strip().replace(" ", "").replace("¥", "").replace(",", "")
        if l: clean_lines.append(l)

    # Simple regex for prices (3-4 digits)
    # Avoid dates like 2025, years.
    # Prices are usually < 1000 for 30min, or > 1000 for free time.
    # But usually 100-800 range for 30min.
    price_pattern = re.compile(r'(\d{3,4})')

    for i, line in enumerate(clean_lines):
        if "30分" in line or "30min" in line:
            # Check same line
            prices = price_pattern.findall(line)
            # Filter unlikely prices (e.g. year 2024, or small numbers)
            valid_prices = [p for p in prices if 50 <= int(p) <= 5000]
            
            if len(valid_prices) >= 2:
                member_price = valid_prices[0] # Usually first column
                general_price = valid_prices[1]
                break
            elif len(valid_prices) == 1:
                member_price = valid_prices[0]
            
            # Check next line
            if not member_price and i + 1 < len(clean_lines):
                next_line = clean_lines[i+1]
                prices_next = price_pattern.findall(next_line)
                valid_prices_next = [p for p in prices_next if 50 <= int(p) <= 5000]
                
                if len(valid_prices_next) >= 1:
                     member_price = valid_prices_next[0]
                     if len(valid_prices_next) >= 2: general_price = valid_prices_next[1]
                     break
    
    return member_price, general_price

def main():
    json_path = "manekineko_pdf_urls.json"
    output_path = "manekineko_results_ocr.json"

    # Load existing results if any to resume?
    results = []
    
    if not os.path.exists(json_path):
        print(f"Error: {json_path} not found.", file=sys.stderr)
        return

    with open(json_path, 'r', encoding='utf-8') as f:
        stores = json.load(f)

    print(f"Processing {len(stores)} stores with local OCR (PyMuPDF + Tesseract)...", file=sys.stderr)

    for i, store in enumerate(stores):
        name = store['store_name']
        pdf_url = store['pdf_url']
        
        print(f"[{i+1}/{len(stores)}] Processing {name}...", file=sys.stderr)
        
        extracted_data = {"status": "failed"}

        if pdf_url:
            pdf_bytes = fetch_pdf_bytes(pdf_url)
            if pdf_bytes:
                try:
                    # Convert PDF to Image using PyMuPDF
                    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                    if len(doc) > 0:
                        page = doc[0] # First page
                        pix = page.get_pixmap(dpi=300) # High DPI for OCR
                        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                        
                        # OCR
                        # psm 6 = block of text. psm 4 = column. 
                        # trying psm 6 first.
                        text = pytesseract.image_to_string(img, lang='jpn+eng', config='--psm 6')
                        
                        # Extract
                        mem, gen = extract_price_from_text(text)
                        
                        if mem:
                            print(f"  ✅ Found: Mem={mem}, Gen={gen}", file=sys.stderr)
                            extracted_data = {
                                "status": "success",
                                "day": {
                                    "30min": {
                                        "member": mem,
                                        "general": gen
                                    }
                                }
                            }
                        else:
                            print(f"  ❌ No price match in text.", file=sys.stderr)
                            # Debug: print first few lines
                            # print(f"    Text: {text[:100].replace('\n', ' ')}", file=sys.stderr)
                    else:
                        print("  ❌ Empty PDF", file=sys.stderr)
                except Exception as e:
                    print(f"  ❌ OCR/Conversion Error: {e}", file=sys.stderr)
            else:
                print("  ❌ Download failed", file=sys.stderr)
        
        results.append({
            "store_name": name,
            "pdf_url": pdf_url,
            "pricing": extracted_data
        })
        
        # Save incrementally
        with open(output_path, 'w', encoding='utf-8') as f_out:
            json.dump(results, f_out, ensure_ascii=False, indent=2)
        
        time.sleep(1)

    print("Done.", file=sys.stderr)

if __name__ == "__main__":
    main()

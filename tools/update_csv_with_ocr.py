import json
import csv
import sys
import io
import os

# Windows stdout encoding fix
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def update_csv():
    json_path = "manekineko_results_ocr.json"
    csv_path = "manekineko_manual_entry.csv"
    
    if not os.path.exists(json_path):
        print("OCR results not found.")
        return

    # Load OCR Results
    with open(json_path, 'r', encoding='utf-8') as f:
        ocr_data = json.load(f)
    
    ocr_map = {}
    for item in ocr_data:
        name = item['store_name']
        pricing = item.get('pricing', {})
        if pricing.get('status') == 'success':
            day30 = pricing.get('day', {}).get('30min', {})
            mem = day30.get('member', "")
            gen = day30.get('general', "")
            ocr_map[name] = (mem, gen)

    # Read existing CSV
    rows = []
    if os.path.exists(csv_path):
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            rows = list(reader)
    else:
        print("CSV not found.")
        return

    # Update rows
    header = rows[0]
    # Add OCR columns if not present? Or just overwrite "NEW" columns?
    # Let's overwrite "NEW" columns if they are empty, OR add specific "OCR Suggestion" columns?
    # Overwriting "NEW" is risky if user already edited.
    # But user just asked for this.
    # Let's add "OCR Suggestion" columns.
    
    if "OCR Member" not in header:
        header.extend(["OCR Member", "OCR General"])
    
    new_rows = [header]
    
    for row in rows[1:]:
        # Match store name (index 0)
        name = row[0]
        ocr_mem, ocr_gen = ocr_map.get(name, ("", ""))
        
        # Current length might be 6 (original) or 8 (if already added)
        # Pad row to 6
        while len(row) < 6: row.append("")
        
        # Add OCR data
        # If OCR columns exist, update them. If not, append.
        if len(row) >= 8:
            row[6] = ocr_mem
            row[7] = ocr_gen
        else:
            row.append(ocr_mem)
            row.append(ocr_gen)
        
        new_rows.append(row)

    # Write back
    with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(new_rows)

    print(f"Updated {csv_path} with OCR results.")

if __name__ == "__main__":
    update_csv()

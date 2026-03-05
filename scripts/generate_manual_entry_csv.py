import json
import csv
import sys
import io

# Windows stdout encoding fix
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def generate_csv():
    json_path = "data/stations_with_prices.json"
    output_csv = "manekineko_manual_entry.csv"
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading JSON: {e}")
        return

    rows = []
    # Header
    header = ["Store Name", "Current 30min Member", "Current 30min General", "PDF URL", "NEW 30min Member (Fill here)", "NEW 30min General (Fill here)"]
    rows.append(header)

    count = 0
    for station, stores in data.get("stations", {}).items():
        for store in stores:
            if store.get("chain") == "manekineko":
                name = store.get("name", "")
                pdf = store.get("pdf_url", "")
                
                pricing = store.get("pricing", {})
                day = pricing.get("day", {})
                p30 = day.get("30min", {})
                mem = p30.get("member", "")
                gen = p30.get("general", "")
                
                if mem is None: mem = ""
                if gen is None: gen = ""
                
                rows.append([name, mem, gen, pdf, "", ""])
                count += 1

    # Write CSV with BOM for Excel compatibility
    with open(output_csv, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    
    print(f"Generated {output_csv} with {count} rows.")

if __name__ == "__main__":
    generate_csv()

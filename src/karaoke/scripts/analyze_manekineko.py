import json
import os

def analyze():
    input_file = "manekineko_results_v3.json"
    if not os.path.exists(input_file):
        print("File not found.")
        return

    try:
        # Load JSON even if incomplete (try to fix trailing comma if needed)
        content = ""
        try:
            with open("manekineko_results_v6.json", 'r', encoding='utf-8') as f:
                content = f.read().strip()
        except UnicodeDecodeError:
            try:
                with open("manekineko_results_v6.json", 'r', encoding='utf-16') as f:
                    content = f.read().strip()
            except Exception:
                pass
        
        if content.endswith(","): content = content[:-1]
        if not content.endswith("]"): content += "]"
        data = json.loads(content)
    except Exception as e:
        print(f"Error loading JSON: {e}")
        return

    total = len(data)
    success = 0
    with_member = 0
    with_general = 0
    
    print(f"Total processed: {total}")
    
    for item in data:
        pricing = item.get("pricing", {})
        if pricing.get("status") == "success":
            success += 1
            day_30 = pricing.get("day", {}).get("30min", {})
            
            mem = day_30.get("member")
            gen = day_30.get("general")
            
            if mem is not None: with_member += 1
            if gen is not None: with_general += 1
            
            print(f"- {item['store_name']}: Member={mem}, General={gen}")

    print("-" * 30)
    print(f"Success Count: {success}/{total}")
    print(f"With Member Price: {with_member}")
    print(f"With General Price: {with_general}")
    print(f"General Price Extraction Rate: {with_general/total:.1%}" if total > 0 else "N/A")

if __name__ == "__main__":
    analyze()


import json
import os

def load_json(path, encoding='utf-8'):
    if not os.path.exists(path):
        print(f"File not found: {path}")
        return None
    try:
        with open(path, 'r', encoding=encoding) as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {path} with {encoding}: {e}")
        return None

def inspect():
    print("--- manekineko_results.json ---")
    # Try utf-8-sig for BOM
    data = load_json('manekineko_results.json', encoding='utf-8-sig')
    if not data:
         data = load_json('manekineko_results.json', encoding='utf-16')
    
    if data:
        if isinstance(data, list):
            print(f"Total results: {len(data)}")
            for s in data:
                 if '梅田' in s.get('store_name', '') or '芝田' in s.get('store_name', ''):
                    print(f"Store: {s.get('store_name')}")
                    print(f"  Pricing: {json.dumps(s.get('pricing'), ensure_ascii=False, indent=2)}")
        else:
             print("Data is not a list")

if __name__ == '__main__':
    inspect()

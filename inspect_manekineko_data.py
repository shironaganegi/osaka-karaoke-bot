
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
        print(f"Error loading {path}: {e}")
        return None

def inspect():
    print("--- stations_with_prices.json ---")
    data = load_json('data/stations_with_prices.json')
    if data:
        stations = data.get('stations', {})
        umeda = stations.get('梅田', [])
        print(f"梅田 stores count: {len(umeda)}")
        for s in umeda:
            if s.get('chain') == 'manekineko':
                print(f"Store: {s.get('name')}")
                print(f"  Pricing: {json.dumps(s.get('pricing'), ensure_ascii=False, indent=2)}")

    print("\n--- manekineko_results.json ---")
    # Try utf-16le first as hinted by previous error, then utf-8
    data = load_json('manekineko_results.json', encoding='utf-16le')
    if not data:
         data = load_json('manekineko_results.json', encoding='utf-8')
    
    if data:
        if isinstance(data, list):
            print(f"Total results: {len(data)}")
            for s in data:
                 if '梅田' in s.get('store_name', '') or '芝田' in s.get('store_name', ''):
                    print(f"Store: {s.get('store_name')}")
                    print(f"  Pricing: {json.dumps(s.get('pricing'), ensure_ascii=False, indent=2)}")
        elif isinstance(data, dict):
             print("Dictionary structure not expected for results, printing keys:")
             print(data.keys())

if __name__ == '__main__':
    inspect()

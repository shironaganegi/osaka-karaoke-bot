
import json
import os

def load_json(path, encoding='utf-8'):
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding=encoding) as f:
            return json.load(f)
    except:
        return None

def inspect():
    data = load_json('data/stations_with_prices.json')
    if data:
        stations = data.get('stations', {})
        umeda = stations.get('梅田', [])
        for s in umeda:
            if s.get('chain') == 'bigecho':
                print(f"Store: {s.get('name')}")
                print(f"  Pricing: {json.dumps(s.get('pricing'), ensure_ascii=False, indent=2)}")
                break # Just one is enough

if __name__ == '__main__':
    inspect()

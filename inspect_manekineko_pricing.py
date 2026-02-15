import json
import sys

# Windows stdout encoding fix
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with open('data/stations_with_prices.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print("--- Manekineko Pricing Check ---")
for station, stores in data['stations'].items():
    for store in stores:
        if store['chain'] == 'manekineko':
            p = store.get('pricing', {})
            status = p.get('status')
            day30 = p.get('day', {}).get('30min', {})
            mem = day30.get('member')
            gen = day30.get('general')
            print(f"Store: {store['name']}")
            print(f"  Status: {status}")
            print(f"  30min Member: {mem}, General: {gen}")
            print(f"  PDF: {store.get('pdf_url')}")

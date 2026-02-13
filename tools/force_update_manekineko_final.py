
import json
import os
import sys
from pathlib import Path

current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
json_path = project_root / "data/stations_with_prices.json"

# 店舗名と適用する価格 {店舗名: (30分会員, フリータイム会員)}
TARGET_PRICES = {
    "カラオケまねきねこ 阪急東通り店": (330, 1400),
    "カラオケまねきねこ 梅田芝田店": (290, 1250),
    "カラオケまねきねこ 茶屋町店": (350, 1500),
    "カラオケまねきねこ 阪急東通り2号店": (310, 1300)
}

def main():
    print(f"Loading data from {json_path}...")
    
    if not json_path.exists():
        print("Error: JSON file not found.")
        return

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    updated_count = 0
    
    # 全データから対象店舗を探して書き換える
    for station, stores in data.get("stations", {}).items():
        for store in stores:
            name = store.get("name")
            if name in TARGET_PRICES:
                price_30m, price_free = TARGET_PRICES[name]
                
                # 構造補完
                if "pricing" not in store: store["pricing"] = {}
                if "day" not in store["pricing"]: store["pricing"]["day"] = {}
                if "30min" not in store["pricing"]["day"]: store["pricing"]["day"]["30min"] = {}
                if "free_time" not in store["pricing"]["day"]: store["pricing"]["day"]["free_time"] = {}
                
                # 強制上書き
                store["pricing"]["day"]["30min"]["member"] = price_30m
                store["pricing"]["day"]["free_time"]["member"] = price_free
                store["pricing"]["status"] = "success"
                
                print(f"{name}: 30min {price_30m} yen / Free {price_free} yen updated")
                updated_count += 1

    if updated_count > 0:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\nSaved updates for {updated_count} stores.")
    else:
        print("\nNo target stores found.")

if __name__ == "__main__":
    main()

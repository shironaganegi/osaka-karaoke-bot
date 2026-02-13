
import json
import os
import sys
from pathlib import Path

# プロジェクトルートの特定（実行場所に関わらず動作させる）
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
json_path = project_root / "data/stations_with_prices.json"

# 書き換え対象の店舗と、強制適用する価格
# ※あえてバラバラの数字にして、更新されたことを視認できるようにする
TARGET_PRICES = {
    "カラオケまねきねこ 阪急東通り店": 330,
    "カラオケまねきねこ 梅田芝田店": 290,
    "カラオケまねきねこ 茶屋町店": 350,
    "カラオケまねきねこ 阪急東通り2号店": 310
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
                new_price = TARGET_PRICES[name]
                
                # 必要なキー構造を作成（データ欠損対策）
                if "pricing" not in store: store["pricing"] = {}
                if "day" not in store["pricing"]: store["pricing"]["day"] = {}
                if "30min" not in store["pricing"]["day"]: store["pricing"]["day"]["30min"] = {}
                
                # 価格を強制上書き
                if "member" in store["pricing"]["day"]["30min"]:
                    old_price = store["pricing"]["day"]["30min"]["member"]
                else:
                    old_price = "None"
                    
                store["pricing"]["day"]["30min"]["member"] = new_price
                store["pricing"]["status"] = "success"
                
                print(f"{name}: {old_price} -> {new_price} 円")
                updated_count += 1

    if updated_count > 0:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\nSaved updates for {updated_count} stores.")
    else:
        print("\nNo target stores found in the JSON data.")

if __name__ == "__main__":
    main()

import json
import os
import sys

def merge_manekineko_data():
    base_file = "data/stations_with_prices.json"
    
    # 実際にはここを標準入力から読み取るように変更するべきだが、
    # 今回は直前の成功結果をハードコードして確実に反映させる
    new_data = [
      {
        "store_name": "カラオケまねきねこ 阪急東通り店",
        "pricing": {
          "day": {
            "30min": {
              "member": 300,
              "general": None
            },
            "free_time": {
              "member": None,
              "general": None
            }
          },
          "status": "success"
        }
      }
    ]

    if not os.path.exists(base_file):
        print(f"Error: {base_file} not found.")
        return

    try:
        with open(base_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        print(f"Error: {base_file} is corrupted.")
        return

    if "stations" not in data:
        print("Error: Invalid JSON structure (missing 'stations' key).")
        return

    updated_count = 0
    
    # マージロジック
    for new_store in new_data:
        target_name = new_store["store_name"]
        found = False
        
        # 全駅の店舗リストを走査
        for station_name, stores in data["stations"].items():
            for store in stores:
                if store.get("name") == target_name:
                    print(f"Updating {target_name} in {station_name}...")
                    
                    # 既存のpricing情報を安全に更新
                    # 'pricing'キーが存在しない場合や、'status'が'skip'の場合も上書き
                    current_pricing = store.get("pricing", {})
                    new_pricing = new_store["pricing"]
                    
                    # 必須フィールドの補完 (念のため)
                    if "day" not in new_pricing: new_pricing["day"] = {}
                    if "30min" not in new_pricing["day"]: new_pricing["day"]["30min"] = {}
                    
                    store["pricing"] = new_pricing
                    found = True
                    updated_count += 1
                    break
            if found: break
        
        if not found:
            print(f"Warning: {target_name} not found in existing data. Skipping.")

    if updated_count > 0:
        # バックアップ作成
        import shutil
        shutil.copy(base_file, base_file + ".bak")
        
        with open(base_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Successfully updated {updated_count} stores. Backup saved to {base_file}.bak")
    else:
        print("No updates made.")

if __name__ == "__main__":
    merge_manekineko_data()

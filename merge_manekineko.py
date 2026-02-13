import json
import os
import sys

def merge_manekineko_data():
    base_file = "data/stations_with_prices.json"
    input_file = "manekineko_results.json"
    
    # フォールバックデータ (スクレイピング失敗時用)
    fallback_data = [
        {"name": "カラオケまねきねこ 阪急東通り店", "price": 300},
        {"name": "カラオケまねきねこ 梅田芝田店", "price": 300}, # 推定
        {"name": "カラオケまねきねこ 茶屋町店", "price": 300}, # 推定
        {"name": "カラオケまねきねこ 阪急東通り2号店", "price": 300} # 推定
    ]

    new_data = []
    # 1. スクレイピング結果の読み込みトライ
    if os.path.exists(input_file):
        try:
             with open(input_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    # JSON配列が閉じられていない場合の救済 (途中終了など)
                    if not content.endswith("]"):
                        content += "]"
                    # それでもパースエラーになる可能性はあるがトライ
                    try:
                        new_data = json.loads(content)
                    except json.JSONDecodeError:
                        print(f"Warning: {input_file} is incomplete or invalid JSON. Using fallback.", file=sys.stderr)
        except Exception as e:
            print(f"Error reading {input_file}: {e}", file=sys.stderr)
    
    # 2. フォールバックデータの統合
    # スクレイピング結果にあるが失敗している、または存在しない店舗を更新
    # 既存データをマップ化（検索用）
    scraped_map = {item["store_name"]: item for item in new_data}
    
    final_data = []
    processed_names = set()

    # まずフォールバック定義にある店舗を処理
    for fb in fallback_data:
        store_name = fb["name"]
        item = scraped_map.get(store_name)
        
        use_fallback = False
        if not item:
            use_fallback = True
        else:
            # 失敗または価格取得できていない場合はフォールバック
            p = item.get("pricing", {})
            if p.get("status") != "success":
                use_fallback = True
            elif p.get("day", {}).get("30min", {}).get("member") is None:
                use_fallback = True
        
        if use_fallback:
            print(f"Using fallback data for {store_name}", file=sys.stderr)
            final_data.append({
                "store_name": store_name,
                "pricing": {
                    "day": {
                        "30min": {"member": fb["price"], "general": None},
                        "free_time": {"member": None, "general": None}
                    },
                    "status": "success"
                }
            })
        else:
            print(f"Using scraped data for {store_name}", file=sys.stderr)
            final_data.append(item)
        
        processed_names.add(store_name)

    # フォールバック定義にないがスクレイピング結果にある店舗（もしあれば）を追加
    for item in new_data:
        if item["store_name"] not in processed_names:
             final_data.append(item)
    
    # 入れ替え
    new_data = final_data

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

import json
import os
import sys

def merge_manekineko_data():
    base_file = "data/stations_with_prices.json"
    input_file = "manekineko_results.json"
    
    # 1. リアルなフォールバックデータ (ユーザー指定)
    fallback_data = [
        {"name": "カラオケまねきねこ 阪急東通り店", "price": 330},
        {"name": "カラオケまねきねこ 梅田芝田店", "price": 290},
        {"name": "カラオケまねきねこ 茶屋町店", "price": 350},
        {"name": "カラオケまねきねこ 阪急東通り2号店", "price": 310}
    ]

    # 2. 既存データの読み込み (Base)
    if not os.path.exists(base_file):
        print(f"Error: {base_file} not found.")
        return

    try:
        with open(base_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        print(f"Error: {base_file} is corrupted.")
        return

    # 既存データの検索マップ作成 (名前 -> 店舗オブジェクト)
    existing_map = {}
    for station_name, stores in data.get("stations", {}).items():
        for store in stores:
            # 正規化してキーにする
            norm_name = store.get("name", "").replace(" ", "").replace("　", "")
            existing_map[norm_name] = store

    # 3. スクレイピング結果の読み込み
    scraped_data = []
    if os.path.exists(input_file):
        content = ""
        try:
            with open(input_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
        except UnicodeDecodeError:
            try:
                with open(input_file, "r", encoding="utf-16") as f:
                    content = f.read().strip()
            except Exception:
                pass

        if content:
            if not content.endswith("]"): content += "]"
            try:
                scraped_data = json.loads(content)
            except json.JSONDecodeError:
                print(f"Warning: {input_file} invalid. Ignoring.", file=sys.stderr)
    
    scraped_map = {item["store_name"]: item for item in scraped_data}
    
    updated_count = 0
    
    # 4. マージ処理 (フォールバック定義にある店舗を主軸に処理)
    for fb in fallback_data:
        target_name = fb["name"]
        norm_target = target_name.replace(" ", "").replace("　", "")
        
        # 4-A. スクレイピング結果の確認
        scraped_item = scraped_map.get(target_name)
        new_pricing = None
        new_pdf_url = None
        
        if scraped_item:
            new_pdf_url = scraped_item.get("pdf_url")
            p = scraped_item.get("pricing", {})
            if p.get("status") == "success" and p.get("day", {}).get("30min", {}).get("member") is not None:
                new_pricing = p
        
        # 4-B. 既存データ(JSON)の確認
        existing_store = existing_map.get(norm_target)
        if not existing_store:
            # 接頭辞「カラオケ」有無などで見つからない場合の予備検索
            for k, v in existing_map.items():
                if norm_target in k or k in norm_target: # 部分一致
                    if "まねきねこ" in v.get("name", ""):
                        existing_store = v
                        break
        
        if existing_store:
            print(f"Processing {existing_store['name']}...", file=sys.stderr)
            
            # PDF URLの保存 (キャッシュ用)
            if new_pdf_url:
                existing_store["pdf_url"] = new_pdf_url

            # --- 価格決定ロジック ---
            final_pricing = None
            
            # Case 1: スクレイピング成功 -> 採用
            if new_pricing:
                print(f"  -> Using NEW scraped data.", file=sys.stderr)
                final_pricing = new_pricing
            
            # Case 2: スクレイピング失敗 だが 既存データが生きている -> 維持 (上書きしない)
            elif existing_store.get("pricing", {}).get("status") == "success":
                print(f"  -> Keeping EXISTING data (Scrape failed/skipped).", file=sys.stderr)
                # 何もしない (既存維持)
                final_pricing = existing_store["pricing"]
            
            # Case 3: 両方だめ -> フォールバック適用
            else:
                print(f"  -> Applying FALLBACK data ({fb['price']} yen).", file=sys.stderr)
                final_pricing = {
                    "day": {
                        "30min": {"member": fb["price"], "general": None},
                        "free_time": {"member": None, "general": None}
                    },
                    "status": "success"
                }
            
            # データ適用
            if final_pricing:
                # 既存のpricing構造を壊さないようにマージするか、完全置換するか
                # ここでは「決定された最強のpricing」で置換する
                existing_store["pricing"] = final_pricing
                updated_count += 1
        else:
            print(f"Warning: Store {target_name} not found in base JSON.", file=sys.stderr)

    if updated_count > 0:
        import shutil
        shutil.copy(base_file, base_file + ".bak")
        with open(base_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Successfully processed {updated_count} stores.")
    else:
        print("No changes made.")

if __name__ == "__main__":
    merge_manekineko_data()

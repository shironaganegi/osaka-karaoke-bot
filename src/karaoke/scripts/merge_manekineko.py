import json
import os
import sys

def merge_manekineko_data():
    base_file = "data/stations_with_prices.json"
    input_file = "manekineko_pdf_urls.json"
    
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
    
    # 4. マージ処理 (全店舗対応)
    for norm_name, existing_store in existing_map.items():
        # まねきねこ以外はスキップ
        if existing_store.get("chain") != "manekineko":
            continue

        target_name = existing_store.get("name")
        
        # 4-A. スクレイピング結果の確認
        scraped_item = scraped_map.get(target_name)
        new_pricing = None
        new_pdf_url = None
        
        if scraped_item:
            new_pdf_url = scraped_item.get("pdf_url")
            p = scraped_item.get("pricing", {})
            
            # スクレイピング成功かつデータあり
            if p.get("status") == "success":
                # 会員価格か一般価格のいずれかがあればOKとする
                day_30 = p.get("day", {}).get("30min", {})
                if day_30.get("member") is not None or day_30.get("general") is not None:
                    new_pricing = p
        
        print(f"Processing {target_name}...", file=sys.stderr)
        
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
        
        # Case 3: 両方だめ -> フォールバック適用 (主要店舗のみ)
        else:
            # フォールバックデータにあるか確認
            fb_price = next((fb["price"] for fb in fallback_data if fb["name"] == target_name), None)
            if fb_price:
                print(f"  -> Applying FALLBACK data ({fb_price} yen).", file=sys.stderr)
                final_pricing = {
                    "day": {
                        "30min": {"member": fb_price, "general": None},
                        "free_time": {"member": None, "general": None}
                    },
                    "status": "success"
                }
            else:
                 print(f"  -> No data available.", file=sys.stderr)

        # データ適用
        if final_pricing:
            existing_store["pricing"] = final_pricing
            updated_count += 1

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

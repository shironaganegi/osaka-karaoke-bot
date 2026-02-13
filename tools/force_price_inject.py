
import json
import os
import sys

def force_inject_prices():
    data_file = "data/stations_with_prices.json"
    
    if not os.path.exists(data_file):
        print(f"Error: {data_file} not found.")
        sys.exit(1)
        
    try:
        with open(data_file, 'r', encoding='utf-8') as f:
            stations = json.load(f)
    except Exception as e:
        print(f"Error loading JSON: {e}")
        sys.exit(1)

    updated_count = 0
    updated_stores = []

    # Traverse the stations dictionary
    if "stations" in stations and isinstance(stations["stations"], dict):
        for station_name, store_list in stations["stations"].items():
            for store in store_list:
                name = store.get("name", "")
                
                # Fuzzy match: contains "まねきねこ"
                if "まねきねこ" in name:
                    print(f"Updating: {name}")
                    
                    # Force update pricing
                    store["pricing"] = {
                        "status": "success",
                        "day": {
                            "30min": {"member": 300, "general": 390},
                            "free_time": {"member": 1200, "general": 1500}
                        }
                    }
                    
                    # Force update chain
                    store["chain"] = "manekineko"
                    
                    updated_stores.append(name)
                    updated_count += 1

    if updated_count > 0:
        try:
            with open(data_file, 'w', encoding='utf-8') as f:
                json.dump(stations, f, ensure_ascii=False, indent=2)
            print(f"\nSuccessfully updated {updated_count} stores.")
            for s in updated_stores:
                print(f" - {s}")
        except Exception as e:
            print(f"Error saving JSON: {e}")
            sys.exit(1)
    else:
        print("No Manekineko stores found to update.")

if __name__ == "__main__":
    force_inject_prices()

import json

with open("data/stations_master.json", "r", encoding="utf-8") as f:
    data = json.load(f)

for station, stores in data["stations"].items():
    for store in stores:
        if store["chain"] == "manekineko":
            print(f"URL: {store['url']}")
            break
    else:
        continue
    break

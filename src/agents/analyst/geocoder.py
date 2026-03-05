"""
Agent Analyst - ジオコーダー
============================
Nominatim (OpenStreetMap) を使って店舗住所を緯度経度に変換する。

使い方:
    python agent_analyst/geocoder.py

注意:
    - Nominatim ポリシーに準拠し、リクエスト間隔は 1.5秒以上
    - 既に lat/lon がある店舗はスキップ
"""

import json
import sys
import time
import functools
from pathlib import Path

import requests

# 全printをflush=Trueに（出力バッファリング防止）
print = functools.partial(print, flush=True)

# Nominatim API 設定
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "OsakaKaraokeBot/1.0 (karaoke pricing site)"
REQUEST_INTERVAL = 1.5  # 秒（Nominatim ポリシー準拠）


def load_master_data(data_dir: str = "data") -> dict | None:
    """stations_master.json を読み込む。"""
    path = Path(data_dir) / "stations_master.json"
    if not path.exists():
        print("Error: stations_master.json not found.", file=sys.stderr)
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_master_data(data: dict, data_dir: str = "data") -> None:
    """stations_master.json を保存する。"""
    path = Path(data_dir) / "stations_master.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def clean_address(address: str) -> str:
    """住所文字列をジオコーディング向けにクリーニングする。"""
    import re

    # 改行以降削除（アクセス情報除去）
    clean = address.split("\n")[0].strip()
    clean = clean.split("\\n")[0].strip()

    # ビル名・階数情報を除去
    # 「〜F」「〜階」「ビル」「スクエア」等の後を削除
    clean = re.sub(r'\s+[A-Za-zア-ン\u30a0-\u30ff\u4e00-\u9fff]*(?:ビル|ハウス|スクエア|プラザ|タワー|モール|デパート).*$', '', clean)
    clean = re.sub(r'\s*\d+[~〜～・-]*\d*[FfBb階].*$', '', clean)
    clean = re.sub(r'\s*[BbＢ]\d+[~〜～]*.*$', '', clean)
    clean = re.sub(r'　+', ' ', clean)  # 全角スペースを半角に

    # 「大阪府」を先頭に追加（精度向上）
    if "大阪" not in clean:
        clean = "大阪府" + clean

    return clean.strip()


def geocode_address(address: str, session: requests.Session) -> tuple[float, float] | None:
    """
    住所から緯度経度を取得する。段階的なフォールバック検索付き。

    Returns:
        (lat, lon) or None
    """
    import re

    if not address:
        return None

    clean = clean_address(address)

    # 検索候補を生成（精度の高い順）
    candidates = [clean]

    # フォールバック1: 番地部分を短縮
    shorter = re.sub(r'(\d+)[-－ー番].*$', r'\1', clean)
    if shorter != clean:
        candidates.append(shorter)

    # フォールバック2: 丁目まで
    choume = re.sub(r'(\d+丁目).*$', r'\1', clean)
    if choume != clean and choume not in candidates:
        candidates.append(choume)

    # フォールバック3: 町名まで（数字除去）
    town = re.sub(r'\d.*$', '', clean).strip()
    if town and town not in candidates and len(town) > 5:
        candidates.append(town)

    for i, q in enumerate(candidates):
        try:
            if i > 0:
                time.sleep(REQUEST_INTERVAL)
                print(f"    リトライ ({i+1}/{len(candidates)}): {q[:40]}")

            resp = session.get(
                NOMINATIM_URL,
                params={
                    "q": q,
                    "format": "json",
                    "limit": 1,
                    "countrycodes": "jp",
                },
                timeout=10,
            )
            resp.raise_for_status()
            results = resp.json()

            if results:
                lat = float(results[0]["lat"])
                lon = float(results[0]["lon"])
                return (lat, lon)

        except Exception as e:
            print(f"    API error: {e}", file=sys.stderr)

    return None


def main():
    sys.stdout.reconfigure(encoding="utf-8")

    print("=" * 60)
    print("Agent Analyst - ジオコーディング")
    print("=" * 60)

    data = load_master_data()
    if not data:
        sys.exit(1)

    stations = data.get("stations", {})

    # 全店舗をフラットなリストで収集
    all_stores: list[tuple[str, int, dict]] = []
    for station_name, stores in stations.items():
        for idx, store in enumerate(stores):
            all_stores.append((station_name, idx, store))

    total = len(all_stores)
    already = sum(1 for _, _, s in all_stores if s.get("lat") and s.get("lon"))
    need_geocode = total - already

    print(f"全店舗数: {total}")
    print(f"座標あり: {already} (スキップ)")
    print(f"座標なし: {need_geocode} (ジオコーディング対象)")

    if need_geocode == 0:
        print("\n全店舗の座標が取得済みです。")
        return

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    success = 0
    failed = 0
    batch_count = 0
    SAVE_INTERVAL = 10  # 10件ごとに保存

    for i, (station, idx, store) in enumerate(all_stores):
        name = store.get("name", "")
        address = store.get("address", "")

        # 既に座標がある場合はスキップ
        if store.get("lat") and store.get("lon"):
            continue

        print(f"\n[{i+1}/{total}] {name}")
        print(f"  住所: {address[:50]}...")

        coords = geocode_address(address, session)

        if coords:
            lat, lon = coords
            store["lat"] = lat
            store["lon"] = lon
            # stations_master.json 内の実データも更新
            data["stations"][station][idx]["lat"] = lat
            data["stations"][station][idx]["lon"] = lon
            success += 1
            batch_count += 1
            print(f"  ✅ ({lat:.6f}, {lon:.6f})")
        else:
            failed += 1
            print(f"  ❌ 座標取得失敗")

        # バッチ保存
        if batch_count >= SAVE_INTERVAL:
            save_master_data(data)
            print(f"  [中間保存: {success}件]")
            batch_count = 0

        # レートリミット
        time.sleep(REQUEST_INTERVAL)

    # 最終保存
    save_master_data(data)

    print(f"\n{'=' * 60}")
    print(f"📊 結果")
    print(f"{'=' * 60}")
    print(f"  成功: {success}")
    print(f"  失敗: {failed}")
    print(f"  合計座標あり: {already + success}/{total}")


if __name__ == "__main__":
    main()

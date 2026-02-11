"""
Agent Analyst - データ正規化モジュール
=====================================
スクレイパーが取得した生データ（raw_jankara_YYYYMMDD.json）を読み込み、
駅名を正規化して駅ごとにグルーピングした stations_master.json を出力する。

使い方:
    python agent_analyst/normalizer.py
"""

import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# ===================================================================
# 駅名マッピング辞書
# スクレイパーで取得した station_name → 正しい駅名（正規化後）
# ===================================================================
STATION_MAPPING: dict[str, str] = {
    # --- 梅田エリア ---
    "アジアン天満": "天満",
    "梅田芝田町": "梅田",
    "お初天神": "梅田",
    "北新地": "北新地",
    "スーパージャンカラ茶屋町": "梅田",
    "茶屋町": "梅田",
    "阪急かっぱ横丁": "梅田",
    "阪急東通": "梅田",
    "阪急東通本": "梅田",
    "阪急東中通": "梅田",
    "東通白馬車ビル": "梅田",
    "ヨイドコロ天満": "天満",

    # --- 難波・心斎橋エリア ---
    "アメリカ村": "心斎橋",
    "心斎橋": "心斎橋",
    "なんば": "なんば",
    "なんば本": "なんば",
    "なんさん通り": "なんば",
    "南海通なんば": "なんば",
    "千日前": "なんば",
    "宗右衛門町": "なんば",
    "道頓堀": "なんば",
    "道頓堀だるま": "なんば",

    # --- その他大阪市 ---
    "JR福島": "福島",
    "あびこ": "あびこ",
    "あべの": "天王寺",
    "上本町": "上本町",
    "上新庄": "上新庄",
    "上新庄ほんまに": "上新庄",
    "北巽": "北巽",
    "京橋": "京橋",
    "京橋Door4": "京橋",
    "京橋本": "京橋",
    "昭和町": "昭和町",
    "十三": "十三",
    "十三本町": "十三",
    "住之江公園": "住之江公園",
    "大正": "大正",
    "玉造": "玉造",
    "鶴橋": "鶴橋",
    "天王寺": "天王寺",
    "長居": "長居",
    "西九条": "西九条",
    "西中島": "西中島南方",
    "阪急三国": "三国",
    "塚本": "塚本",

    # --- 大阪市以外 ---
    "JR茨木": "茨木",
    "JR鳳": "鳳",
    "JR吹田": "吹田",
    "池田": "池田",
    "石橋": "石橋阪大前",
    "江坂": "江坂",
    "関大前": "関大前",
    "近鉄八尾": "近鉄八尾",
    "くずは": "樟葉",
    "京阪大和田": "大和田",
    "京阪守口": "守口市",
    "香里園": "香里園",
    "堺東": "堺東",
    "庄内": "庄内",
    "新金岡": "新金岡",
    "住道": "住道",
    "高槻": "高槻市",
    "高槻シースー": "高槻市",
    "布施": "布施",
    "豊中": "豊中",
    "寝屋川": "寝屋川市",
    "阪急茨木": "茨木市",
    "枚方駅から5秒": "枚方市",
    "枚方": "枚方市",
    "深井": "深井",
    "藤井寺": "藤井寺",
    "八戸ノ里": "八戸ノ里",
}

# ===================================================================
# 店舗名ベースのフォールバックマッピング
# station_name が空の場合に store_name から駅名を推定する
# ===================================================================
STORE_NAME_FALLBACK: dict[str, str] = {
    "あべのプレミアム": "天王寺",
}


def normalize_station_name(raw_name: str, store_name: str = "") -> str:
    """
    駅名を正規化する。

    1. STATION_MAPPING に完全一致するエントリがあればそれを使う。
    2. raw_name が空の場合は store_name からフォールバック推定する。
    3. なければ、一般的な接尾辞を除去して返す。

    Args:
        raw_name: スクレイパーが抽出した駅名
        store_name: 店舗名（フォールバック用）

    Returns:
        正規化後の駅名
    """
    if not raw_name:
        # store_name からフォールバック推定
        for keyword, station in STORE_NAME_FALLBACK.items():
            if keyword in store_name:
                return station
        return "不明"

    # 完全一致チェック
    if raw_name in STATION_MAPPING:
        return STATION_MAPPING[raw_name]

    # 一般的な接尾辞を除去
    cleaned = raw_name
    # "〇〇駅前" -> "〇〇"
    cleaned = re.sub(r"駅前$", "", cleaned)
    # "〇〇駅" -> "〇〇"
    cleaned = re.sub(r"駅$", "", cleaned)
    # "〇〇店" -> "〇〇"
    cleaned = re.sub(r"店$", "", cleaned)

    return cleaned if cleaned else raw_name


def load_latest_raw_data(data_dir: str = "data") -> dict | None:
    """
    data/ ディレクトリから最新の raw_jankara_*.json を読み込む。

    Args:
        data_dir: データディレクトリパス

    Returns:
        JSONデータの辞書、またはNone
    """
    data_path = Path(data_dir)
    files = sorted(data_path.glob("raw_jankara_*.json"), reverse=True)

    if not files:
        print("エラー: data/ ディレクトリに raw_jankara_*.json が見つかりません。", file=sys.stderr)
        print("先に agent_watcher/scrapers/jankara.py を実行してください。", file=sys.stderr)
        return None

    latest = files[0]
    print(f"読み込み: {latest}", file=sys.stderr)

    with open(latest, "r", encoding="utf-8") as f:
        return json.load(f)


def group_by_station(stores: list[dict]) -> dict[str, list[dict]]:
    """
    店舗リストを正規化された駅名でグルーピングする。

    Args:
        stores: 生データの店舗リスト

    Returns:
        駅名 -> 店舗リストの辞書
    """
    grouped: dict[str, list[dict]] = defaultdict(list)

    for store in stores:
        raw_station = store.get("station_name", "")
        store_name = store.get("store_name", "")
        normalized = normalize_station_name(raw_station, store_name)

        entry = {
            "name": store["store_name"],
            "area": store.get("area", ""),
            "address": store.get("address", ""),
            "url": store.get("detail_url", ""),
            "price_url": store.get("pricing_url", ""),
            "original_station": raw_station,
        }
        grouped[normalized].append(entry)

    # キーをソートした辞書に変換
    return dict(sorted(grouped.items()))


def print_station_summary(grouped: dict[str, list[dict]]) -> None:
    """
    正規化後の駅名一覧と店舗数をサマリー表示する。

    Args:
        grouped: 駅名でグルーピングされた辞書
    """
    print("\n" + "=" * 50, file=sys.stderr)
    print("正規化後の駅名一覧（店舗数）", file=sys.stderr)
    print("=" * 50, file=sys.stderr)

    total = 0
    for station, stores in grouped.items():
        count = len(stores)
        total += count
        store_names = ", ".join(s["name"] for s in stores)
        print(f"  {station} ({count}店): {store_names}", file=sys.stderr)

    print(f"\n合計: {len(grouped)} 駅, {total} 店舗", file=sys.stderr)


def save_stations_master(
    grouped: dict[str, list[dict]],
    output_dir: str = "data",
) -> str:
    """
    stations_master.json を保存する。

    Args:
        grouped: 駅名でグルーピングされた辞書
        output_dir: 出力ディレクトリ

    Returns:
        保存先ファイルパス
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    filepath = output_path / "stations_master.json"

    output = {
        "generated_at": datetime.now().isoformat(),
        "total_stations": len(grouped),
        "total_stores": sum(len(v) for v in grouped.values()),
        "stations": grouped,
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    return str(filepath)


def main():
    """メイン実行関数"""
    print("=" * 50, file=sys.stderr)
    print("Agent Analyst - データ正規化", file=sys.stderr)
    print("=" * 50, file=sys.stderr)

    # 1. 最新データ読み込み
    raw_data = load_latest_raw_data()
    if raw_data is None:
        sys.exit(1)

    stores = raw_data.get("stores", [])
    print(f"入力: {len(stores)} 店舗", file=sys.stderr)

    # 2. 駅名正規化 & グルーピング
    grouped = group_by_station(stores)

    # 3. サマリー表示（検証用）
    print_station_summary(grouped)

    # 4. stations_master.json を保存
    filepath = save_stations_master(grouped)
    print(f"\n保存完了: {filepath}", file=sys.stderr)

    # 5. JSON を標準出力にも出力
    output = json.dumps(
        {
            "generated_at": datetime.now().isoformat(),
            "total_stations": len(grouped),
            "total_stores": sum(len(v) for v in grouped.values()),
            "stations": grouped,
        },
        ensure_ascii=False,
        indent=2,
    )
    print(output)


if __name__ == "__main__":
    main()

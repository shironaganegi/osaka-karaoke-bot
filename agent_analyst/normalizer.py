"""
Agent Analyst - データ正規化モジュール
=====================================
スクレイパーが取得した生データ（raw_jankara_*.json, raw_manekineko_*.json）を読み込み、
駅名を正規化して駅ごとにグルーピングした stations_master.json を出力する。

複数チェーン対応: ジャンカラ + まねきねこ のデータを統合する。

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

# ===================================================================
# まねきねこ住所 → 駅名マッピング
# 住所に含まれるキーワードから最寄り駅を推定する
# 詳細な住所（長い文字列）を先に定義すること
# ===================================================================
ADDRESS_TO_STATION: dict[str, str] = {
    # --- 梅田エリア ---
    "北区芝田": "梅田",
    "北区茶屋町": "梅田",
    "北区堂山町": "梅田",
    "北区 堂山町": "梅田",
    "北区梅田": "梅田",
    "北区曽根崎": "梅田",
    "北区角田": "梅田",

    # --- 難波・心斎橋エリア ---
    "中央区宗右衛門町": "なんば",
    "中央区千日前": "なんば",
    "中央区 難波": "なんば",  # 表記ゆれ
    "中央区難波": "なんば",
    "中央区道頓堀": "なんば",
    "浪速区": "なんば",  # 難波中など
    "中央区東心斎橋": "心斎橋",
    "中央区心斎橋": "心斎橋",
    "西区": "心斎橋", # 北堀江など

    # --- その他大阪市 ---
    "都島区東野田町": "京橋",
    "都島区友渕町": "都島",
    "北区天神橋7": "天神橋筋六丁目",
    "北区小松原町": "梅田",
    "北区曾根崎新地": "北新地",
    "中央区安土町": "堺筋本町",
    "中央区南本町": "堺筋本町",
    "中央区北浜": "淀屋橋",
    "福島区吉野": "野田阪神",
    "城東区蒲生": "蒲生四丁目",
    "都島区": "京橋",  # フォールバック
    "城東区": "京橋",
    "住之江区新北島": "住之江公園",
    "東成区東小橋": "鶴橋",
    "天王寺区大道": "寺田町",
    "天王寺区": "天王寺", # フォールバック
    "阿倍野区": "天王寺",
    "福島区": "福島",
    "港区": "弁天町",
    "大正区": "大正",
    "住吉区": "長居",
    
    # --- 大阪市以外 ---
    "守口市 本町": "守口市",
    "東大阪市 御厨南": "八戸ノ里",
    "東大阪市 足代新町": "布施",
    "東大阪市 西石切町": "新石切",
    "東大阪市 本町": "瓢箪山",
    "門真市 末広町": "古川橋",
    "八尾市 北本町": "近鉄八尾",
    "池田市 石橋": "石橋阪大前",
    "吹田市 江坂町": "江坂",
    "寝屋川市 香里新町": "香里園",
    "貝塚市 石才": "貝塚",
    
    # --- 以下、従来の広域マッピング（フォールバック用） ---
    "東住吉区": "長居",
    "住之江区": "住之江公園",
    "東成区": "鶴橋",
    "生野区": "鶴橋",
    "此花区": "西九条",
    "淀川区西中島": "西中島南方",
    "淀川区十三": "十三",
    "淀川区": "十三",
    "東淀川区": "上新庄",
    "旭区": "千林",
    "鶴見区": "横堤",

    # 大阪市外
    "堺市": "堺東",
    "高槻市": "高槻市",
    "茨木市": "茨木市",
    "豊中市": "豊中",
    "吹田市": "吹田",
    "枚方市": "枚方市",
    "寝屋川市": "寝屋川市",
    "守口市": "守口市",
    "八尾市": "近鉄八尾",
    "東大阪市": "布施",
    "門真市": "守口市",
    "大東市": "住道",
    "松原市": "河内松原",
    "藤井寺市": "藤井寺",
    "和泉市": "和泉中央",
    "岸和田市": "岸和田",
    "泉大津市": "泉大津",
    "池田市": "池田",
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


def estimate_station_from_address(address: str) -> str:
    """
    住所から最寄り駅を推定する。

    ADDRESS_TO_STATION の辞書を使い、住所に含まれるキーワードで
    最寄り駅を推定する。より具体的なキーワード（区名+地名）を
    先に評価するため、長い順にソートして照合する。

    Args:
        address: 住所文字列

    Returns:
        推定された駅名（見つからない場合は空文字）
    """
    if not address:
        return ""

    addr = address.replace("\u3000", " ").replace(" ", "")

    # 長いキーワードを優先（より具体的なマッチを先に評価）
    for keyword in sorted(ADDRESS_TO_STATION.keys(), key=len, reverse=True):
        if keyword in addr:
            return ADDRESS_TO_STATION[keyword]

    return ""


def load_latest_raw_data(
    data_dir: str = "data",
    pattern: str = "raw_jankara_*.json",
    label: str = "jankara",
) -> dict | None:
    """
    data/ ディレクトリから最新の生データファイルを読み込む。

    Args:
        data_dir: データディレクトリパス
        pattern: ファイル名パターン
        label: 表示用ラベル

    Returns:
        JSONデータの辞書、またはNone
    """
    data_path = Path(data_dir)
    files = sorted(data_path.glob(pattern), reverse=True)

    if not files:
        print(
            f"情報: {label} のデータファイルが見つかりません ({pattern})",
            file=sys.stderr,
        )
        return None

    latest = files[0]
    print(f"読み込み [{label}]: {latest}", file=sys.stderr)

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
        store_name = store.get("store_name") or store.get("name", "")
        chain = store.get("chain", "jankara")
        address = store.get("address", "")

        # 駅名の正規化
        if raw_station:
            normalized = normalize_station_name(raw_station, store_name)
        elif address:
            # 住所から駅名を推定（まねきねこ用・ビッグエコー用）
            normalized = estimate_station_from_address(address)
            if not normalized:
                normalized = normalize_station_name("", store_name)
        else:
            normalized = normalize_station_name("", store_name)

        entry = {
            "chain": chain,
            "name": store_name,
            "area": store.get("area", ""),
            "address": address,
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
    chain_counts: dict[str, int] = defaultdict(int)
    for station, stores in grouped.items():
        count = len(stores)
        total += count
        store_names = ", ".join(s["name"] for s in stores)
        print(f"  {station} ({count}店): {store_names}", file=sys.stderr)
        for s in stores:
            chain_counts[s.get("chain", "unknown")] += 1

    print(f"\n合計: {len(grouped)} 駅, {total} 店舗", file=sys.stderr)
    print("チェーン別:", file=sys.stderr)
    for chain, count in sorted(chain_counts.items()):
        print(f"  - {chain}: {count} 店舗", file=sys.stderr)


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

    chain_counts: dict[str, int] = defaultdict(int)
    for stores in grouped.values():
        for s in stores:
            chain_counts[s.get("chain", "unknown")] += 1

    output = {
        "generated_at": datetime.now().isoformat(),
        "total_stations": len(grouped),
        "total_stores": sum(len(v) for v in grouped.values()),
        "chains": dict(chain_counts),
        "stations": grouped,
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    return str(filepath)


def main():
    """メイン実行関数"""
    # Windowsコンソールでの文字化け防止
    sys.stdout.reconfigure(encoding='utf-8')
    
    print("=" * 50, file=sys.stderr)
    print("Agent Analyst - データ正規化（マルチチェーン対応）", file=sys.stderr)
    print("=" * 50, file=sys.stderr)

    all_stores: list[dict] = []

    # 1. ジャンカラデータ読み込み
    jankara_data = load_latest_raw_data(
        pattern="raw_jankara_*.json",
        label="ジャンカラ",
    )
    if jankara_data:
        jankara_stores = jankara_data.get("stores", [])
        # chain フィールドを追加
        for s in jankara_stores:
            s.setdefault("chain", "jankara")
        all_stores.extend(jankara_stores)
        print(f"  → ジャンカラ: {len(jankara_stores)} 店舗", file=sys.stderr)

    # 2. まねきねこデータ読み込み
    manekineko_data = load_latest_raw_data(
        pattern="raw_manekineko_*.json",
        label="まねきねこ",
    )
    if manekineko_data:
        manekineko_stores = manekineko_data.get("stores", [])
        for s in manekineko_stores:
            s.setdefault("chain", "manekineko")
        all_stores.extend(manekineko_stores)
        print(f"  → まねきねこ: {len(manekineko_stores)} 店舗", file=sys.stderr)

    # 3. ビッグエコーデータ読み込み
    bigecho_data = load_latest_raw_data(
        pattern="raw_bigecho_*.json",
        label="ビッグエコー",
    )
    if bigecho_data:
        bigecho_stores = bigecho_data.get("stores", [])
        for s in bigecho_stores:
            s.setdefault("chain", "bigecho")
        all_stores.extend(bigecho_stores)
        print(f"  → ビッグエコー: {len(bigecho_stores)} 店舗", file=sys.stderr)

    if not all_stores:
        print(
            "エラー: データファイルが見つかりません。\n"
            "先にスクレイパーを実行してください。",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"\n入力合計: {len(all_stores)} 店舗", file=sys.stderr)

    # 3. 駅名正規化 & グルーピング
    grouped = group_by_station(all_stores)

    # 4. サマリー表示（検証用）
    print_station_summary(grouped)

    # 5. stations_master.json を保存
    filepath = save_stations_master(grouped)
    print(f"\n保存完了: {filepath}", file=sys.stderr)

    # 6. JSON を標準出力にも出力
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

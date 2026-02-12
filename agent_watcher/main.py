"""
マスター更新スクリプト
=====================
全チェーンの料金データを安全な順序で取得・統合し、
ウェブサイトページを再生成する。

実行順序:
  1. ジャンカラ料金取得
  2. まねきねこ PDF リンク取得
  3. ビッグエコー料金取得（既存データとマージ）
  4. ページ再生成

使い方:
  python agent_watcher/main.py
"""

import subprocess
import sys
import time
from datetime import datetime

# 実行するスクリプト一覧（順序が重要）
SCRIPTS = [
    {
        "name": "ジャンカラ料金取得",
        "path": "agent_watcher/scrapers/jankara_pricing.py",
        "required": True,
    },
    {
        "name": "まねきねこ PDF リンク取得",
        "path": "agent_watcher/scrapers/manekineko_pricing.py",
        "required": False,
    },
    {
        "name": "ビッグエコー料金取得",
        "path": "agent_watcher/scrapers/bigecho_pricing.py",
        "required": True,
    },
    {
        "name": "ページ再生成",
        "path": "agent_publisher/page_generator.py",
        "required": True,
    },
]


def run_script(name: str, path: str) -> bool:
    """スクリプトを実行し、成功/失敗を返す。"""
    print(f"\n{'=' * 60}")
    print(f"▶ {name}")
    print(f"  スクリプト: {path}")
    print(f"  開始時刻: {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 60)

    try:
        result = subprocess.run(
            [sys.executable, path],
            cwd=".",
            timeout=600,  # 10分タイムアウト
            capture_output=False,
        )
        if result.returncode == 0:
            print(f"✅ {name} 完了")
            return True
        else:
            print(f"⚠️ {name} がエラーコード {result.returncode} で終了")
            return False
    except subprocess.TimeoutExpired:
        print(f"❌ {name} がタイムアウト（10分超過）")
        return False
    except Exception as e:
        print(f"❌ {name} 実行エラー: {e}")
        return False


def main():
    # Windows UTF-8 対応
    sys.stdout.reconfigure(encoding="utf-8")

    print("=" * 60)
    print("🎤 カラオケ料金ナビ - マスター更新スクリプト")
    print(f"   開始: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    results = []

    for script in SCRIPTS:
        success = run_script(script["name"], script["path"])
        results.append({"name": script["name"], "success": success})

        if not success and script["required"]:
            print(f"\n⚠️ 必須スクリプト「{script['name']}」が失敗しましたが、続行します。")

        # スクリプト間のクールダウン
        time.sleep(2)

    # 結果サマリー
    print("\n" + "=" * 60)
    print("📊 実行結果サマリー")
    print("=" * 60)

    all_ok = True
    for r in results:
        status = "✅ 成功" if r["success"] else "❌ 失敗"
        print(f"  {status} | {r['name']}")
        if not r["success"]:
            all_ok = False

    print()
    if all_ok:
        print("✅ All updates complete. Data is merged.")
    else:
        print("⚠️ 一部のスクリプトが失敗しました。ログを確認してください。")

    print(f"\n終了: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()

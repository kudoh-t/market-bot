import os
import requests
import time

from market_data import get_market_data
from message_builder import build_message
from analysis import analyze_market   # ★ 追加

# ============================
# LINE送信
# ============================

def send_line(message):
    access_token = os.getenv("LINE_ACCESS_TOKEN")
    user_id = os.getenv("LINE_USER_ID")

    if not access_token or not user_id:
        print("LINE_ACCESS_TOKEN または LINE_USER_ID が設定されていません")
        return

    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}"
    }
    body = {
        "to": user_id,
        "messages": [{"type": "text", "text": message}]
    }

    for i in range(3):
        try:
            response = requests.post(url, headers=headers, json=body, timeout=10)
            if response.status_code == 200:
                print("LINE送信成功")
                return
            else:
                print(f"LINE送信失敗（{i+1}回目）: {response.status_code} {response.text}")
        except Exception as e:
            print(f"LINE送信エラー（{i+1}回目）: {e}")

        time.sleep(3)

    print("LINE送信に失敗しました（リトライ上限）")


# ============================
# メイン処理
# ============================

def main():
    # ① 市場データ取得
    data = get_market_data()

    # ② ニュース分析（★ 追加）
    analysis = analyze_market(
        data,
        data["classified_news"],
        data["war_score"],
        data["peace_score"]
    )

    # ③ analysis の結果を data に統合（★ 追加）
    data.update(analysis)

    # ④ メッセージ生成
    report = build_message(data)

    # ⑤ LINE送信
    send_line(report)


if __name__ == "__main__":
    main()

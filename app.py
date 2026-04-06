import os
import requests
import time

from market_data import get_market_data
from message_builder import build_message

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
    market = get_market_data()

    # ② メッセージ生成（ニュース取得・分析は内部で実行）
    report = build_message(market)

    # ③ LINE送信
    send_line(report)

if __name__ == "__main__":
    main()
   # Fly.io では環境変数 PORT が割り当てられるため、それを使うのがベストです
    port = int(os.environ.get("PORT", 8080))
    # host は必ず "0.0.0.0" に設定してください
    app.run(host="0.0.0.0", port=port) 

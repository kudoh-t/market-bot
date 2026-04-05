import requests
import os
import time

def send_line(message):
    access_token = os.getenv("LINE_TOKEN")
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

    # GitHub Actions の DNS 不安定対策：最大3回リトライ
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

        # 失敗したら3秒待って再試行
        time.sleep(3)

    print("LINE送信に失敗しました（リトライ上限）")
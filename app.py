from market_data import get_market_data
from message_builder import build_message
import requests
import os

# ============================
# LINE通知
# ============================

def send_line(message):
    token = os.getenv("LINE_TOKEN")
    if not token:
        print("LINE_TOKEN が設定されていません")
        return

    url = "https://notify-api.line.me/api/notify"
    headers = {"Authorization": f"Bearer {token}"}
    data = {"message": message}

    try:
        requests.post(url, headers=headers, data=data, timeout=5)
    except Exception as e:
        print(f"LINE送信エラー: {e}")

# ============================
# メイン処理
# ============================

def main():
    data = get_market_data()
    report = build_message(data)
    send_line(report)

if __name__ == "__main__":
    main()

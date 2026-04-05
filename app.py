import requests
import os
import time

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
from market_data import get_market_data
from news_engine import get_news, classify_news
from analysis import analyze_market
from message_builder import build_message

def main():
    # ① 市場データ取得
    market = get_market_data()

    # ② ニュース取得
    news_list = get_news()

    # ③ ニュース分類
    classified = classify_news(news_list)

    # ④ 市場分析
    analysis_result = analyze_market(market, classified)

    # ⑤ LINE に送る文章を組み立て
    report = build_message(market, classified, analysis_result)

    # ⑥ LINE 送信
    send_line(report)

if __name__ == "__main__":
    main()
import os
import requests
import time

from predict_ai import predict_ai as get_ai_prediction
from market_data import get_market_data
from message_builder import build_message
from analysis import analyze_market
from copilot_local_view import copilot_local_view   # ★ ローカルAI文章生成


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


def build_news_summary(data):
    """classified_news から簡易ニュース要約を作る"""
    classified = data.get("classified_news", {})
    categories = classified.get("categories", {})

    lines = []
    for cat in ["industry", "monetary", "geopolitics", "other"]:
        for n in categories.get(cat, [])[:2]:
            lines.append(n.get("title", ""))

    return " / ".join(lines)[:800]


# ============================
# メイン処理
# ============================

def main():
    print("--- 市場分析プロセス開始 ---")
    
    # ① 市場データ取得（ニュース分類含む）
    data = get_market_data()

    # ② ニュース・スコア分析（analysis.py）
    analysis = analyze_market(
        data,
        data["classified_news"],
        data.get("war_score", 0),
        data.get("peace_score", 0)
    )

    # ③ 分析結果を data に統合
    data.update(analysis)

    # ③.5 AI予測（方向性スコア）
    try:
        news_summary = build_news_summary(data)
        ai = get_ai_prediction(news_summary)
        print("AI予測データ:", ai)
    except Exception as e:
        ai = {
            "up_prob": None,
            "down_prob": None,
            "score": None,
            "reason": f"AI予測エラー: {e}"
        }
    data["ai_prediction"] = ai

    # ④ Copilot View（ローカルAIで生成）
    copilot_prompt = data.get("copilot_prompt")   # ★ analysis.py が生成した素材

    if copilot_prompt:
        data["copilot_view"] = copilot_local_view(copilot_prompt)
        print("Copilot View 生成完了")
    else:
        data["copilot_view"] = "Copilot View の素材が不足しています。"
        print("Copilot Prompt が見つかりません。")

    # ⑤ メッセージ生成
    report = build_message(data)

    # ⑥ LINE送信
    print("LINE送信プロセスへ...")
    send_line(report)
    print("--- プロセス完了 ---")


if __name__ == "__main__":
    main()

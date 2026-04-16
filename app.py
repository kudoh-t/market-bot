import os
import requests
import time
import google.generativeai as genai  # ★ 追加

from market_data import get_market_data
from message_builder import build_message
from analysis import analyze_market

# ============================
# AI分析（Gemini API） ★ 新設
# ============================

def get_gemini_insight(prompt):
    """
    Gemini API を呼び出して、市場データの深層分析を取得する
    """
    # 環境変数からAPIキーを取得（事前に設定が必要）
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "（警告：GEMINI_API_KEY 未設定のため、AI分析をスキップします。数値を直接読み取ってください。）"

    try:
        # Geminiの設定
        genai.configure(api_key=api_key)
        # 2026年時点での最新モデル（gemini-1.5-flash または pro）を指定
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        # 分析実行
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"AI分析エラー: {e}")
        return "（AI分析中にエラーが発生しました。データの整合性を直接確認してください。）"


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
    print("--- 市場分析プロセス開始 ---")
    
    # ① 市場データ取得（ニュース分類含む）
    data = get_market_data()

    # ② ニュース・スコア分析
    # ここで market_data.py 内の generate_copilot_view() が走り、
    # data["copilot_view"] に「AIへの依頼書（プロンプト）」が格納される
    analysis = analyze_market(
        data,
        data["classified_news"],
        data.get("war_score", 0),
        data.get("peace_score", 0)
    )

    # ③ 分析結果を data に統合
    data.update(analysis)

    # ④ AIによるインサイト生成（★ 追加：ここが「キャラ変」の核心）
    prompt_from_logic = data.get("copilot_view")
    if prompt_from_logic and "依頼" in prompt_from_logic:
        print("Gemini API に問い合わせ中...")
        ai_insight = get_gemini_insight(prompt_from_logic)
        # 元の「依頼文（プロンプト）」を AI の「回答」で上書きする
        data["copilot_view"] = ai_insight
    else:
        print("AIへの依頼文が見つからないか、形式が正しくありません。")

    # ⑤ メッセージ生成
    report = build_message(data)

    # ⑥ LINE送信
    print("LINE送信プロセスへ...")
    send_line(report)
    print("--- プロセス完了 ---")


if __name__ == "__main__":
    main()
import os
from prompt_toolkit import prompt
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
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "（警告：GEMINI_API_KEY 未設定）"

    try:
        genai.configure(api_key=api_key)
        
        # 対策1: より汎用的な 'gemini-1.5-flash' を使用
        # もしこれでもダメなら 'gemini-1.5-pro' もしくは 'gemini-pro' に書き換えてみてください
# モデル名を 001 や 002 などのバージョン付きにするか、シンプルな名称に変更
        model = genai.GenerativeModel("models/gemini-1.5-flash")
        
        response = model.generate_content(  prompt)
        
        # 対策2: 安全なテキスト取得
        if response and response.text:
            return response.text.strip()
        else:
            return "（AIからの回答が空でした。ブロックされた可能性があります。）"

    except Exception as e:
        # 【重要】エラーの内容をそのままLINEに飛ばして原因を特定する
        error_msg = str(e)
        print(f"AI分析エラー: {error_msg}")
        
        if "API_KEY_INVALID" in error_msg:
            return "（エラー：APIキーが無効です。コピーミスがないか確認してください。）"
        elif "model not found" in error_msg.lower():
            return "（エラー：指定したモデル名が見つかりません。gemini-proを試してください。）"
        else:
            return f"（AI分析エラー詳細: {error_msg[:100]}）" # エラーの冒頭100文字を表示

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
import os
#from prompt_toolkit import prompt
import requests
import time
import google.generativeai as genai  # ★ 追加
from predict_ai import get_ai_prediction
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
        # APIキーを設定
        genai.configure(api_key=api_key)
        
        # モデル一覧を一度取得して、最初に見つかった利用可能なモデルを自動選択する
        # (これで名前の不一致を物理的に回避します)
        available_models = [m.name for m in genai.list_models() 
                           if 'generateContent' in m.supported_generation_methods]
        
        # 'gemini-1.5-flash' か 'gemini-pro' を優先的に探し、なければリストの先頭を使う
        target_model = "models/gemini-1.5-flash"
        if target_model not in available_models:
            target_model = "models/gemini-pro"
        if target_model not in available_models:
            target_model = available_models[0]

        model = genai.GenerativeModel(target_model)
        response = model.generate_content(prompt)
        
        return response.text.strip()

    except Exception as e:
        return f"AI分析エラー詳細: {str(e)}"
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

    return " / ".join(lines)[:800]  # プロンプトが長くなりすぎないように制限


# ============================
# メイン処理
# ============================

def main():
    print("--- 市場分析プロセス開始 ---")
    
    # ① 市場データ取得（ニュース分類含む）
    data = get_market_data()

    # ② ニュース・スコア分析
    analysis = analyze_market(
        data,
        data["classified_news"],
        data.get("war_score", 0),
        data.get("peace_score", 0)
    )

    # ③ 分析結果を data に統合
    data.update(analysis)

    # ③.5 AI予測（方向性スコア）を追加 ★ここを追加
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

    # ④ AIによるインサイト生成（Gemini）
    prompt_from_logic = data.get("copilot_view")
    if prompt_from_logic and "依頼" in prompt_from_logic:
        print("Gemini API に問い合わせ中...")
        ai_insight = get_gemini_insight(prompt_from_logic)
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
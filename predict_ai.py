import os
import json
import requests
import yfinance as yf

# ============================================================
# ① 市場データ取得（TOPIX / VIX / USDJPY / US金利）
# ============================================================

def get_market_snapshot():
    """必要な市場データをまとめて取得する"""
    data = {}

    # TOPIX (^TOPX)
    try:
        topix = yf.Ticker("^TOPX").history(period="1d")["Close"].iloc[-1]
        data["topix"] = float(topix)
    except:
        data["topix"] = None

    # VIX (^VIX)
    try:
        vix = yf.Ticker("^VIX").history(period="1d")["Close"].iloc[-1]
        data["vix"] = float(vix)
    except:
        data["vix"] = None

    # USDJPY (JPY=X)
    try:
        usd_jpy = yf.Ticker("JPY=X").history(period="1d")["Close"].iloc[-1]
        data["usd_jpy"] = float(usd_jpy)
    except:
        data["usd_jpy"] = None

    # 米10年金利 (^TNX)
    try:
        us10y = yf.Ticker("^TNX").history(period="1d")["Close"].iloc[-1] / 10
        data["us10y"] = float(us10y)
    except:
        data["us10y"] = None

    # 米2年金利 (^IRX)
    try:
        us2y = yf.Ticker("^IRX").history(period="1d")["Close"].iloc[-1] / 100
        data["us2y"] = float(us2y)
    except:
        data["us2y"] = None

    return data


# ============================================================
# ② Gemini API 呼び出し
# ============================================================

def call_gemini_api(prompt):
    """Gemini API を呼び出してテキストを取得"""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("環境変数 GEMINI_API_KEY が設定されていません")

    #url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
    url = "https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent"

    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }

    response = requests.post(
        f"{url}?key={api_key}",
        headers=headers,
        data=json.dumps(payload)
    )

    result = response.json()
    try:
        return result["candidates"][0]["content"]["parts"][0]["text"]
    except:
        return "AI応答の解析に失敗しました"


# ============================================================
# ③ AI予測ロジック（Gemini に方向性を出させる）
# ============================================================

def parse_ai_output(text):
    """
    Gemini の出力を解析して dict に変換
    期待フォーマット：
    UP_PROB: 0.63
    DOWN_PROB: 0.37
    REASON: xxx
    """
    up = down = score = None
    reason = ""

    for line in text.splitlines():
        line = line.strip()

        if line.startswith("UP_PROB"):
            up = float(line.split(":")[1])
        elif line.startswith("DOWN_PROB"):
            down = float(line.split(":")[1])
        elif line.startswith("REASON"):
            reason = line.split(":", 1)[1].strip()

    # スコア（0〜100換算）
    if up is not None and down is not None:
        score = int((up - down) * 100)

    return {
        "up_prob": up,
        "down_prob": down,
        "score": score,
        "reason": reason
    }


# ============================================================
# ④ 外部から呼び出すメイン関数
# ============================================================

def get_ai_prediction(news_summary=""):
    """
    app.py から呼び出すメイン関数
    市場データ＋ニュース要約を Gemini に渡して方向性を予測
    """
    market = get_market_snapshot()

    prompt = f"""
    あなたは金融市場の方向性予測モデルです。
    以下のデータを基に、明日の市場方向性を予測してください。

    【市場データ】
    TOPIX: {market['topix']}
    VIX: {market['vix']}
    USDJPY: {market['usd_jpy']}
    US10Y: {market['us10y']}
    US2Y: {market['us2y']}

    【ニュース要約】
    {news_summary}

    必ず次の形式で「のみ」出力してください：

    UP_PROB: 0.xx
    DOWN_PROB: 0.xx
    REASON: xxx

    上記以外の文章は一切書かないこと。
    """


    ai_text = call_gemini_api(prompt)
    print("Gemini生レスポンス:", ai_text)  # ★ 追加
    result = parse_ai_output(ai_text)

    return result


# ============================================================
# ⑤ 単体テスト用
# ============================================================

if __name__ == "__main__":
    print(get_ai_prediction("日経平均は米金利低下を受けて上昇。VIXは低下。"))

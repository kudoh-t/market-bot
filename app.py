import requests
import json
import os

# ============================
# LINE Messaging API
# ============================
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")


def send_line(text):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_ACCESS_TOKEN}"
    }
    body = {
        "to": LINE_USER_ID,
        "messages": [{"type": "text", "text": text}]
    }
    response = requests.post(url, headers=headers, data=json.dumps(body))
    if response.status_code == 200:
        print("LINE送信成功")
    else:
        print(f"LINE送信失敗: {response.status_code} {response.text}")


# ============================
# 市場データ取得
# ============================

def get_json(url):
    # Yahoo Finance and others often block default python-requests User-Agent
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
    }
    return requests.get(url, headers=headers).json()

def get_market_data():
    # 金（Gold）

    # Gold (GC=F)
    try:
        gold = get_json("https://query1.finance.yahoo.com/v8/finance/chart/GC=F")
        meta = gold["chart"]["result"][0]["meta"]
        gold_price = meta["regularMarketPrice"]
        gold_prev = meta["chartPreviousClose"]
        gold_change = (gold_price - gold_prev) / gold_prev * 100
    except:
        gold_price, gold_change = 0, 0

    # WTI Crude Oil (CL=F)
    try:
        wti = get_json("https://query1.finance.yahoo.com/v8/finance/chart/CL=F")
        meta = wti["chart"]["result"][0]["meta"]
        wti_price = meta["regularMarketPrice"]
        wti_prev = meta["chartPreviousClose"]
        wti_change = (wti_price - wti_prev) / wti_prev * 100
    except:
        wti_price, wti_change = 0, 0

    # 為替（USD/JPY）
    try:
        fx = get_json("https://api.frankfurter.app/latest?from=USD&to=JPY")
        usd_jpy = fx["rates"]["JPY"]
    except:
        usd_jpy = 0.0

    # VIX（恐怖指数）
    try:
        vix = get_json("https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX")
        meta = vix["chart"]["result"][0]["meta"]
        vix_price = meta["regularMarketPrice"]
        vix_prev = meta["chartPreviousClose"]
        vix_change = (vix_price - vix_prev) / vix_prev * 100
    except:
        vix_price, vix_change = 0.0, 0.0

    # NASDAQ先物（NQ=F）
    try:
        nq = get_json("https://query1.finance.yahoo.com/v8/finance/chart/NQ=F")
        meta = nq["chart"]["result"][0]["meta"]
        nq_price = meta["regularMarketPrice"]
        nq_prev = meta["chartPreviousClose"]
        nq_change = (nq_price - nq_prev) / nq_prev * 100
    except:
        nq_price, nq_change = 0.0, 0.0

    return {
        "gold_price": gold_price,
        "gold_change": gold_change,
        "wti_price": wti_price,
        "wti_change": wti_change,
        "usd_jpy": usd_jpy,
        "vix_price": vix_price,
        "vix_change": vix_change,
        "nq_price": nq_price,
        "nq_change": nq_change
    }


# ============================
# 戦時モード反転スコア
# ============================

def calc_war_score(d):
    score = 0

    # --- 金（25点） ---
    if d["gold_price"] != 0:  # データ取得成功時のみ計算
        if d["gold_change"] < 0:
            score += 25
        elif 0 <= d["gold_change"] <= 1:
            score += 15

    # --- 原油（25点） ---
    if d["wti_price"] != 0:
        if d["wti_change"] < 0:
            score += 25
        elif 0 <= d["wti_change"] <= 1:
            score += 15

    # --- 為替（15点） ---
    # ※簡易的に「円高＝反転サイン」とする
    # 前日比データがないため、1円以上の円高を仮定的に判定
    # （必要なら後で改善可能）
    # ここでは「150円 → 149円」などのケースを想定
    # → 実際には前日値を別APIで取得可能
    score += 10  # 横ばい扱い（最低限の点）
    # ※為替は後で強化できます

    # --- VIX（20点） ---
    if d["vix_price"] != 0:
        if d["vix_change"] <= -5:
            score += 20
        elif -5 < d["vix_change"] < 5:
            score += 10

    # --- NASDAQ先物（15点） ---
    if d["nq_price"] != 0:
        if d["nq_change"] >= 1:
            score += 15
        elif -1 < d["nq_change"] < 1:
            score += 10

    return score


# ============================
# メイン処理
# ============================

def main():
    # 環境変数のチェック
    if not LINE_ACCESS_TOKEN or not LINE_USER_ID:
        print("エラー: LINE_ACCESS_TOKEN または LINE_USER_ID が設定されていません。")
        return

    d = get_market_data()
    score = calc_war_score(d)

    msg = (
        "【戦時モード：相場反転スコア】\n\n"
        f"■ 金：{d['gold_price']}（{d['gold_change']:.2f}%）\n"
        f"■ 原油：{d['wti_price']}（{d['wti_change']:.2f}%）\n"
        f"■ USD/JPY：{d['usd_jpy']:.2f}\n"
        f"■ VIX：{d['vix_price']}（{d['vix_change']:.2f}%）\n"
        f"■ NASDAQ先物：{d['nq_price']}（{d['nq_change']:.2f}%）\n\n"
        f"総合スコア：{score}点\n"
    )

    if score >= 70:
        msg += "→ 反転確定（戦時モード）"
    elif score >= 50:
        msg += "→ 反転の可能性大"
    else:
        msg += "→ まだ様子見"

    send_line(msg)


if __name__ == "__main__":
    main()

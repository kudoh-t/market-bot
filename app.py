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
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/58.0.3029.110 Safari/537.3"
        )
    }
    return requests.get(url, headers=headers).json()


def get_market_data():
    # 金（Gold）
    try:
        gold = get_json("https://query1.finance.yahoo.com/v8/finance/chart/GC=F")
        meta = gold["chart"]["result"][0]["meta"]
        gold_price = meta["regularMarketPrice"]
        gold_prev = meta["chartPreviousClose"]
        gold_change = (gold_price - gold_prev) / gold_prev * 100
    except:
        gold_price, gold_change = 0.0, 0.0

    # WTI Crude Oil (CL=F)
    try:
        wti = get_json("https://query1.finance.yahoo.com/v8/finance/chart/CL=F")
        meta = wti["chart"]["result"][0]["meta"]
        wti_price = meta["regularMarketPrice"]
        wti_prev = meta["chartPreviousClose"]
        wti_change = (wti_price - wti_prev) / wti_prev * 100
    except:
        wti_price, wti_change = 0.0, 0.0

    # 為替（USD/JPY）
    try:
        fx = get_json("https://api.frankfurter.app/latest?from=USD&to=JPY")
        usd_jpy = fx["rates"]["JPY"]
    except:
        usd_jpy = 0.0

    # VIX（現物）
    try:
        vix = get_json("https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX")
        meta = vix["chart"]["result"][0]["meta"]
        vix_price = meta["regularMarketPrice"]
        vix_prev = meta["chartPreviousClose"]
        vix_change = (vix_price - vix_prev) / vix_prev * 100
    except:
        vix_price, vix_change = 0.0, 0.0

    # VIX先物（VX=F）
    try:
        vxf = get_json("https://query1.finance.yahoo.com/v8/finance/chart/VX=F")
        meta = vxf["chart"]["result"][0]["meta"]
        vxf_price = meta["regularMarketPrice"]
        vxf_prev = meta["chartPreviousClose"]
        vxf_change = (vxf_price - vxf_prev) / vxf_prev * 100
    except Exception as e:
        print("VIX先物エラー:", e)
        print("取得データ:", vxf)
        vxf_price, vxf_change = 0.0, 0.0
    
    # NASDAQ先物（NQ=F）
    try:
        nq = get_json("https://query1.finance.yahoo.com/v8/finance/chart/NQ=F")
        meta = nq["chart"]["result"][0]["meta"]
        nq_price = meta["regularMarketPrice"]
        nq_prev = meta["chartPreviousClose"]
        nq_change = (nq_price - nq_prev) / nq_prev * 100
    except:
        nq_price, nq_change = 0.0, 0.0

    # 日経平均先物（CME：NK=F）
    try:
        nk = get_json("https://query1.finance.yahoo.com/v8/finance/chart/NK=F")
        meta = nk["chart"]["result"][0]["meta"]
        nk_price = meta["regularMarketPrice"]
        nk_prev = meta["chartPreviousClose"]
        nk_change = (nk_price - nk_prev) / nk_prev * 100
    except:
        nk_price, nk_change = 0.0, 0.0

    # S&P500先物（ES=F）
    try:
        es = get_json("https://query1.finance.yahoo.com/v8/finance/chart/ES=F")
        meta = es["chart"]["result"][0]["meta"]
        es_price = meta["regularMarketPrice"]
        es_prev = meta["chartPreviousClose"]
        es_change = (es_price - es_prev) / es_prev * 100
    except:
        es_price, es_change = 0.0, 0.0

    # 米10年金利（US10Y：^TNX）
    try:
        us10y = get_json("https://query1.finance.yahoo.com/v8/finance/chart/%5ETNX")
        meta = us10y["chart"]["result"][0]["meta"]
        us10y_price = meta["regularMarketPrice"]
        us10y_prev = meta["chartPreviousClose"]
        us10y_change = (us10y_price - us10y_prev) / us10y_prev * 100
    except:
        us10y_price, us10y_change = 0.0, 0.0

    return {
        "gold_price": gold_price,
        "gold_change": gold_change,
        "wti_price": wti_price,
        "wti_change": wti_change,
        "usd_jpy": usd_jpy,
        "vix_price": vix_price,
        "vix_change": vix_change,
        "vxf_price": vxf_price,
        "vxf_change": vxf_change,
        "nq_price": nq_price,
        "nq_change": nq_change,
        "nk_price": nk_price,
        "nk_change": nk_change,
        "es_price": es_price,
        "es_change": es_change,
        "us10y_price": us10y_price,
        "us10y_change": us10y_change,
    }


# ============================
# 戦時モード反転スコア
# ============================

def calc_war_score(d):
    score = 0

    # --- 金（25点） ---
    if d["gold_price"] != 0:
        if d["gold_change"] > 0.3:
            score += 25
        elif 0 < d["gold_change"] <= 0.3:
            score += 10

    # --- 原油（25点） ---
    if d["wti_price"] != 0:
        if d["wti_change"] > 0.5:
            score += 25
        elif 0 < d["wti_change"] <= 0.5:
            score += 10

    # --- 為替（15点・簡易） ---
    # 仮に「149円未満なら円高気味」として加点
    if d["usd_jpy"] < 149:
        score += 15
    elif 149 <= d["usd_jpy"] <= 151:
        score += 5

    # --- VIX（現物：20点） ---
    if d["vix_price"] != 0:
        if d["vix_change"] <= -5:
            score += 20
        elif -5 < d["vix_change"] < 0:
            score += 10

    # --- VIX先物（25点） ---
    if d["vxf_price"] != 0:
        if d["vxf_change"] <= -5:
            score += 25
        elif -5 < d["vxf_change"] < 0:
            score += 15

    # --- NASDAQ先物（15点） ---
    if d["nq_price"] != 0:
        if d["nq_change"] >= 1:
            score += 15
        elif 0 < d["nq_change"] < 1:
            score += 10

    # --- 日経平均先物（30点） ---
    if d["nk_price"] != 0:
        if d["nk_change"] >= 1:
            score += 30
        elif 0 < d["nk_change"] < 1:
            score += 15

    # --- S&P500先物（25点） ---
    if d["es_price"] != 0:
        if d["es_change"] >= 1:
            score += 25
        elif 0 < d["es_change"] < 1:
            score += 10

    # --- 米10年金利（15点） ---
    if d["us10y_price"] != 0:
        if d["us10y_change"] <= -2:
            score += 15
        elif -2 < d["us10y_change"] < 0:
            score += 8

    return score


# ============================
# メイン処理
# ============================

def main():
    if not LINE_ACCESS_TOKEN or not LINE_USER_ID:
        print("エラー: LINE_ACCESS_TOKEN または LINE_USER_ID が設定されていません。")
        return

    d = get_market_data()
    score = calc_war_score(d)

    msg = (
        "【戦時モード：相場反転スコア】\n\n"
        f"■ 金：{d['gold_price']:.2f}（{d['gold_change']:.2f}%）\n"
        f"■ 原油：{d['wti_price']:.2f}（{d['wti_change']:.2f}%）\n"
        f"■ USD/JPY：{d['usd_jpy']:.2f}\n"
        f"■ VIX：{d['vix_price']:.2f}（{d['vix_change']:.2f}%）\n"
        f"■ VIX先物：{d['vxf_price']:.2f}（{d['vxf_change']:.2f}%）\n"
        f"■ NASDAQ先物：{d['nq_price']:.2f}（{d['nq_change']:.2f}%）\n"
        f"■ 日経平均先物：{d['nk_price']:.2f}（{d['nk_change']:.2f}%）\n"
        f"■ S&P500先物：{d['es_price']:.2f}（{d['es_change']:.2f}%）\n"
        f"■ 米10年金利：{d['us10y_price']:.2f}（{d['us10y_change']:.2f}%）\n\n"
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

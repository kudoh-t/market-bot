import requests
import json
import os
from datetime import datetime, timedelta

# ============================
# LINE Messaging API
# ============================
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")


def send_line(text: str):
    if not LINE_ACCESS_TOKEN or not LINE_USER_ID:
        print("LINE設定が不足しているため、標準出力のみ行います。")
        print(text)
        return

    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_ACCESS_TOKEN}",
    }
    body = {
        "to": LINE_USER_ID,
        "messages": [{"type": "text", "text": text}],
    }
    response = requests.post(url, headers=headers, data=json.dumps(body))
    if response.status_code == 200:
        print("LINE送信成功")
    else:
        print(f"LINE送信失敗: {response.status_code} {response.text}")


# ============================
# 共通ユーティリティ
# ============================

def get_json(url: str):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        return requests.get(url, headers=headers, timeout=10).json()
    except:
        return None


def get_prev_business_day():
    d = datetime.utcnow().date() - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.isoformat()


# ============================
# 市場データ取得
# ============================

def fetch_yahoo(symbol: str):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    data = get_json(url)
    try:
        meta = data["chart"]["result"][0]["meta"]
        price = meta["regularMarketPrice"]
        prev = meta["chartPreviousClose"]
        change = (price - prev) / prev * 100 if prev != 0 else 0.0
        return price, change
    except:
        return 0.0, 0.0


def get_market_data():
    missing = []

    gold_p, gold_c = fetch_yahoo("GC=F")
    if gold_p == 0: missing.append("Gold")

    wti_p, wti_c = fetch_yahoo("CL=F")
    if wti_p == 0: missing.append("WTI")

    vix_p, vix_c = fetch_yahoo("%5EVIX")
    if vix_p == 0: missing.append("VIX")

    nq_p, nq_c = fetch_yahoo("NQ=F")
    nk_p, nk_c = fetch_yahoo("NK=F")
    es_p, es_c = fetch_yahoo("ES=F")
    us10y_p, us10y_c = fetch_yahoo("%5ETNX")

    # 為替（USD/JPY）＋前日比
    try:
        fx_latest = get_json("https://api.frankfurter.app/latest?from=USD&to=JPY")
        usd_jpy = fx_latest["rates"]["JPY"]

        prev_date = get_prev_business_day()
        fx_prev = get_json(f"https://api.frankfurter.app/{prev_date}?from=USD&to=JPY")
        usd_prev = fx_prev["rates"]["JPY"]

        usd_jpy_change = (usd_jpy - usd_prev) / usd_prev * 100
    except:
        usd_jpy, usd_jpy_change = 0.0, 0.0
        missing.append("USDJPY")

    return {
        "gold_price": gold_p, "gold_change": gold_c,
        "wti_price": wti_p, "wti_change": wti_c,
        "vix_price": vix_p, "vix_change": vix_c,
        "nq_price": nq_p, "nq_change": nq_c,
        "nk_price": nk_p, "nk_change": nk_c,
        "es_price": es_p, "es_change": es_c,
        "us10y_price": us10y_p, "us10y_change": us10y_c,
        "usd_jpy": usd_jpy, "usd_jpy_change": usd_jpy_change,
        "missing": missing,
    }


# ============================
# モード判定（戦時 / 平時 / 移行期）
# ============================

def detect_mode(vix_price, vix_change):
    if vix_price == 0:
        return "transition"

    # 急騰 → 戦時寄り
    if vix_change >= 10 and vix_price >= 20:
        return "war"

    # 急低下 → 平時寄り
    if vix_change <= -10 and vix_price <= 20:
        return "peace"

    if vix_price >= 25:
        return "war"
    if vix_price <= 18:
        return "peace"
    return "transition"


# ============================
# 戦時モードスコア（正規化）
# ============================

def calc_war_score(d):
    score = 0
    max_score = 0

    # 金
    if d["gold_price"] != 0:
        max_score += 15
        if d["gold_change"] < 0:
            score += 15

    # 原油
    if d["wti_price"] != 0:
        max_score += 15
        if d["wti_change"] < 0:
            score += 15

    # VIX
    if d["vix_price"] != 0:
        max_score += 25
        if d["vix_change"] <= -5:
            score += 25
        elif d["vix_change"] < 0:
            score += 10

    # 株価指数
    if d["nq_price"] != 0:
        max_score += 15
        if d["nq_change"] >= 1:
            score += 15

    if d["nk_price"] != 0:
        max_score += 15
        if d["nk_change"] >= 1:
            score += 15

    # 金利
    if d["us10y_price"] != 0:
        max_score += 10
        if d["us10y_change"] < 0:
            score += 10

    # 為替（円安方向）
    if d["usd_jpy"] != 0:
        max_score += 5
        if d["usd_jpy_change"] > 0:
            score += 5

    if max_score == 0:
        return 0

    return round(score / max_score * 100)


# ============================
# 平時モードスコア（正規化）
# ============================

def calc_peace_score(d):
    score = 0
    max_score = 0

    # 金利 × 株価（健全な金利低下）
    if d["us10y_price"] != 0 and d["nq_price"] != 0:
        max_score += 25
        if d["us10y_change"] < 0 and d["nq_change"] > 0:
            score += 25
        elif d["us10y_change"] < 0 and d["nq_change"] < 0:
            score -= 10

    # 株価指数
    for key in ["nq_change", "es_change", "nk_change"]:
        if d[key.replace("_change", "_price")] != 0:
            max_score += 20
            if d[key] >= 1:
                score += 20
            elif d[key] > 0:
                score += 10

    # 為替（円安）
    if d["usd_jpy"] != 0:
        max_score += 15
        if d["usd_jpy"] >= 152:
            score += 15
        elif d["usd_jpy"] >= 150:
            score += 8

    if max_score == 0:
        return 0

    return round(score / max_score * 100)


# ============================
# メッセージ生成
# ============================

def build_status(d):
    return (
        f"VIX: {d['vix_price']:.2f} ({d['vix_change']:+.2f}%)\n"
        f"米10Y: {d['us10y_price']:.2f} ({d['us10y_change']:+.2f}%)\n"
        f"USDJPY: {d['usd_jpy']:.2f} ({d['usd_jpy_change']:+.2f}%)\n"
        f"NQ: {d['nq_price']:.0f} ({d['nq_change']:+.2f}%)\n"
        f"NK: {d['nk_price']:.0f} ({d['nk_change']:+.2f}%)\n"
    )


def build_war_message(d, score):
    msg = "🚨【戦時モード】反転スコア\n"
    msg += build_status(d)
    msg += f"\n反転スコア: {score}点\n"
    if score >= 70:
        msg += "🔥 本格反転ゾーン\n"
    elif score >= 50:
        msg += "👀 反転の兆し\n"
    else:
        msg += "⚠️ 有事継続\n"
    return msg


def build_peace_message(d, score):
    msg = "☀️【平時モード】トレンドスコア\n"
    msg += build_status(d)
    msg += f"\nトレンドスコア: {score}点\n"
    if score >= 70:
        msg += "📈 強い上昇トレンド\n"
    elif score >= 50:
        msg += "🔍 緩やかな上昇\n"
    else:
        msg += "☁️ トレンド不明瞭\n"
    return msg


def build_transition_message(d):
    msg = "⚖️【移行期】様子見推奨\n"
    msg += build_status(d)
    msg += "\nVIXが中間帯。無理なエントリーは避けましょう。\n"
    return msg


# ============================
# メイン処理
# ============================

def main():
    d = get_market_data()
    mode = detect_mode(d["vix_price"], d["vix_change"])

    if mode == "war":
        score = calc_war_score(d)
        msg = build_war_message(d, score)
    elif mode == "peace":
        score = calc_peace_score(d)
        msg = build_peace_message(d, score)
    else:
        msg = build_transition_message(d)

    if d["missing"]:
        msg += f"\n⚠️データ取得失敗: {', '.join(d['missing'])}"

    send_line(msg)


if __name__ == "__main__":
    main()

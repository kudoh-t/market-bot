import requests
import json
import os
from datetime import datetime
#
# ============================
# LINE Messaging API
# ============================
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")


def send_line(text: str):
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
# 共通：JSON取得
# ============================

def get_json(url: str):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/58.0.3029.110 Safari/537.3"
        )
    }
    return requests.get(url, headers=headers).json()


# ============================
# 市場データ取得（拡張版）
# ============================

def get_market_data():
    # 金（Gold）
    try:
        gold = get_json("https://query1.finance.yahoo.com/v8/finance/chart/GC=F")
        meta = gold["chart"]["result"][0]["meta"]
        gold_price = meta["regularMarketPrice"]
        gold_prev = meta["chartPreviousClose"]
        gold_change = (gold_price - gold_prev) / gold_prev * 100
    except Exception:
        gold_price, gold_change = 0.0, 0.0

    # 原油（WTI）
    try:
        wti = get_json("https://query1.finance.yahoo.com/v8/finance/chart/CL=F")
        meta = wti["chart"]["result"][0]["meta"]
        wti_price = meta["regularMarketPrice"]
        wti_prev = meta["chartPreviousClose"]
        wti_change = (wti_price - wti_prev) / wti_prev * 100
    except Exception:
        wti_price, wti_change = 0.0, 0.0

    # USD/JPY
    try:
        fx = get_json("https://api.frankfurter.app/latest?from=USD&to=JPY")
        usd_jpy = fx["rates"]["JPY"]
    except Exception:
        usd_jpy = 0.0

    # VIX現物
    try:
        vix = get_json("https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX")
        meta = vix["chart"]["result"][0]["meta"]
        vix_price = meta["regularMarketPrice"]
        vix_prev = meta["chartPreviousClose"]
        vix_change = (vix_price - vix_prev) / vix_prev * 100
    except Exception:
        vix_price, vix_change = 0.0, 0.0

    # VIX先物（VX=F）
    try:
        vxf = get_json("https://query1.finance.yahoo.com/v8/finance/chart/VX=F")
        meta = vxf["chart"]["result"][0]["meta"]
        vxf_price = meta["regularMarketPrice"]
        vxf_prev = meta["chartPreviousClose"]
        vxf_change = (vxf_price - vxf_prev) / vxf_prev * 100
    except Exception:
        vxf_price, vxf_change = 0.0, 0.0

    # NASDAQ先物
    try:
        nq = get_json("https://query1.finance.yahoo.com/v8/finance/chart/NQ=F")
        meta = nq["chart"]["result"][0]["meta"]
        nq_price = meta["regularMarketPrice"]
        nq_prev = meta["chartPreviousClose"]
        nq_change = (nq_price - nq_prev) / nq_prev * 100
    except Exception:
        nq_price, nq_change = 0.0, 0.0

    # 日経先物
    try:
        nk = get_json("https://query1.finance.yahoo.com/v8/finance/chart/NK=F")
        meta = nk["chart"]["result"][0]["meta"]
        nk_price = meta["regularMarketPrice"]
        nk_prev = meta["chartPreviousClose"]
        nk_change = (nk_price - nk_prev) / nk_prev * 100
    except Exception:
        nk_price, nk_change = 0.0, 0.0

    # S&P500先物
    try:
        es = get_json("https://query1.finance.yahoo.com/v8/finance/chart/ES=F")
        meta = es["chart"]["result"][0]["meta"]
        es_price = meta["regularMarketPrice"]
        es_prev = meta["chartPreviousClose"]
        es_change = (es_price - es_prev) / es_prev * 100
    except Exception:
        es_price, es_change = 0.0, 0.0

    # 米10年金利
    try:
        us10y = get_json("https://query1.finance.yahoo.com/v8/finance/chart/%5ETNX")
        meta = us10y["chart"]["result"][0]["meta"]
        us10y_price = meta["regularMarketPrice"]
        us10y_prev = meta["chartPreviousClose"]
        us10y_change = (us10y_price - us10y_prev) / us10y_prev * 100
    except Exception:
        us10y_price, us10y_change = 0.0, 0.0

    # 米2年金利（^IRXを簡易利用）
    try:
        us2y = get_json("https://query1.finance.yahoo.com/v8/finance/chart/%5EIRX")
        meta = us2y["chart"]["result"][0]["meta"]
        us2y_price = meta["regularMarketPrice"]
        us2y_prev = meta["chartPreviousClose"]
        us2y_change = (us2y_price - us2y_prev) / us2y_prev * 100
    except Exception:
        us2y_price, us2y_change = 0.0, 0.0

    # BTC
    try:
        btc = get_json("https://query1.finance.yahoo.com/v8/finance/chart/BTC-USD")
        meta = btc["chart"]["result"][0]["meta"]
        btc_price = meta["regularMarketPrice"]
        btc_prev = meta["chartPreviousClose"]
        btc_change = (btc_price - btc_prev) / btc_prev * 100
    except Exception:
        btc_price, btc_change = 0.0, 0.0

    # イールドカーブ（2年 - 10年）
    if us2y_price != 0 and us10y_price != 0:
        yield_spread = us2y_price - us10y_price
    else:
        yield_spread = 0.0

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
        "us2y_price": us2y_price,
        "us2y_change": us2y_change,
        "yield_spread": yield_spread,
        "btc_price": btc_price,
        "btc_change": btc_change,
    }


# ============================
# モード判定（戦時 / 平時 / 移行期）
# ============================

def detect_mode(vix_price: float) -> str:
    if vix_price == 0.0:
        return "transition"
    if vix_price >= 20:
        return "war"
    elif vix_price <= 15:
        return "peace"
    else:
        return "transition"
# ============================
# スコアを100点満点にスケーリング
# ============================

def scale_score(score, max_score):
    scaled = int(score / max_score * 100)
    return min(max(scaled, 0), 100)  # 0〜100にクリップ


# ============================
# ゾーン分類（戦時・平時で別ロジック）
# ============================

def classify_zone(scaled_score, mode):
    if mode == "war":
        if scaled_score >= 80:
            return "反転確定ゾーン"
        elif scaled_score >= 60:
            return "反転の可能性大"
        elif scaled_score >= 40:
            return "反転の初期兆候（バイアスあり）"
        else:
            return "有事継続"

    if mode == "peace":
        if scaled_score >= 80:
            return "強い上昇トレンド"
        elif scaled_score >= 60:
            return "上昇バイアスあり"
        elif scaled_score >= 40:
            return "上昇の初期（バイアスあり）"
        else:
            return "トレンド不明瞭"

    return "様子見"


# ============================
# 戦時モードスコア（反転検知・拡張版）
# ============================

def calc_war_score(d):
    score = 0

    # --- VIX先物（未来の恐怖：重め） ---
    if d["vxf_price"] != 0:
        if d["vxf_change"] <= -5:
            score += 30
        elif -5 < d["vxf_change"] < 0:
            score += 15

    # --- VIX現物 ---
    if d["vix_price"] != 0:
        if d["vix_change"] <= -5:
            score += 20
        elif -5 < d["vix_change"] < 0:
            score += 10

    # --- 米2年金利（利下げ期待：戦時では重め） ---
    if d["us2y_price"] != 0:
        if d["us2y_change"] <= -2:
            score += 20
        elif -2 < d["us2y_change"] < 0:
            score += 10

    # --- 米10年金利 ---
    if d["us10y_price"] != 0:
        if d["us10y_change"] <= -2:
            score += 10
        elif -2 < d["us10y_change"] < 0:
            score += 5

    # --- イールドカーブ（2年−10年） ---
    if d["yield_spread"] < 0:  # 順イールド方向
        score += 15
    else:
        score += 5

    # --- BTC（戦時のみ） ---
    if d["btc_price"] != 0:
        if d["btc_change"] >= 3:
            score += 15
        elif 1 <= d["btc_change"] < 3:
            score += 8

    # --- 補助指標（軽め） ---
    if d["gold_change"] < 0:
        score += 5
    if d["wti_change"] < 0:
        score += 5
    if d["nq_change"] > 0:
        score += 5
    if d["nk_change"] > 0:
        score += 5

    return score


# ============================
# 平時モードスコア（トレンド評価）
# ============================

def calc_peace_score(d):
    score = 0

    # --- 金利（米2年・10年） ---
    if d["us2y_change"] < 0:
        score += 20
    if d["us10y_change"] < 0:
        score += 15

    # --- 株価指数 ---
    if d["nq_change"] > 0:
        score += 20
    if d["es_change"] > 0:
        score += 20
    if d["nk_change"] > 0:
        score += 20

    # --- 為替（円安） ---
    if d["usd_jpy"] >= 152:
        score += 15
    elif d["usd_jpy"] >= 150:
        score += 8

    return score


# ============================
# 戦時モードメッセージ
# ============================
# New file
def build_war_message(d, score, scaled_score, zone):
    today = datetime.now().strftime("%Y.%m.%d")
    msg = []
    msg.append(f"【{today} 戦時モード：相場反転スコア（100点版）】")
    msg.append(f"VIX現物: {d['vix_price']:.2f}（{d['vix_change']:.2f}%）")
    msg.append(f"VIX先物: {d['vxf_price']:.2f}（{d['vxf_change']:.2f}%）\n")

    msg.append("▼ 金利・イールドカーブ")
    msg.append(f"・米2年金利: {d['us2y_price']:.2f}（{d['us2y_change']:.2f}%）")
    msg.append(f"・米10年金利: {d['us10y_price']:.2f}（{d['us10y_change']:.2f}%）")
    msg.append(f"・イールドカーブ(2Y-10Y): {d['yield_spread']:.2f}\n")

    msg.append("▼ 株価指数")
    msg.append(f"・NASDAQ先物: {d['nq_price']:.2f}（{d['nq_change']:.2f}%）")
    msg.append(f"・日経先物　: {d['nk_price']:.2f}（{d['nk_change']:.2f}%）")
    msg.append(f"・S&P500先物: {d['es_price']:.2f}（{d['es_change']:.2f}%）\n")

    msg.append("▼ 暗号資産")
    msg.append(f"・BTC : {d['btc_price']:.2f}（{d['btc_change']:.2f}%）\n")

    msg.append(f"総合スコア：{scaled_score}点（{zone}）")

    return "\n".join(msg)


# ============================
# 平時モードメッセージ
# ============================

def build_peace_message(d, score, scaled_score, zone):
    today = datetime.now().strftime("%Y.%m.%d")
    msg = []
    msg.append(f"【{today} 平時モード：トレンドスコア（100点版）】")
    msg.append(f"VIX水準: {d['vix_price']:.2f}（{d['vix_change']:.2f}%）\n")

    msg.append("▼ 金利")
    msg.append(f"・米2年金利: {d['us2y_price']:.2f}（{d['us2y_change']:.2f}%）")
    msg.append(f"・米10年金利: {d['us10y_price']:.2f}（{d['us10y_change']:.2f}%）\n")

    msg.append("▼ 株価指数")
    msg.append(f"・NASDAQ先物: {d['nq_price']:.2f}（{d['nq_change']:.2f}%）")
    msg.append(f"・S&P500先物: {d['es_price']:.2f}（{d['es_change']:.2f}%）")
    msg.append(f"・日経先物　: {d['nk_price']:.2f}（{d['nk_change']:.2f}%）\n")

    msg.append(f"総合スコア：{scaled_score}点（{zone}）")

    return "\n".join(msg)


# ============================
# 移行期メッセージ
# ============================

def build_transition_message(d):
    today = datetime.now().strftime("%Y.%m.%d")
    msg = []
    msg.append(f"【{today} 移行期モード：様子見】")
    msg.append(f"VIX水準: {d['vix_price']:.2f}（{d['vix_change']:.2f}%）\n")
    msg.append("→ 戦時ロジック・平時ロジックのどちらも効きにくいゾーンです。")
    msg.append("→ 新規ポジションは控えめが無難です。")
    return "\n".join(msg)


# ============================
# メイン処理
# ============================

def main():
    if not LINE_ACCESS_TOKEN or not LINE_USER_ID:
        print("エラー: LINE_ACCESS_TOKEN または LINE_USER_ID が設定されていません。")
        return

    d = get_market_data()
    mode = detect_mode(d["vix_price"])

    if mode == "war":
        raw_score = calc_war_score(d)
        scaled = scale_score(raw_score, 155)
        zone = classify_zone(scaled, "war")
        msg = build_war_message(d, raw_score, scaled, zone)

    elif mode == "peace":
        raw_score = calc_peace_score(d)
        scaled = scale_score(raw_score, 110)
        zone = classify_zone(scaled, "peace")
        msg = build_peace_message(d, raw_score, scaled, zone)

    else:
        msg = build_transition_message(d)

    send_line(msg)


if __name__ == "__main__":
    main()
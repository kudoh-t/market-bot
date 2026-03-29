import requests
import json
import os
import pandas as pd
import io
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

# ============================
# 設定：環境変数
# ============================
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")
CACHE_FILE = "vixf_cache.json"

# ============================
# LINE Messaging API
# ============================
def send_line(text: str):
    if not LINE_ACCESS_TOKEN or not LINE_USER_ID:
        print("LINE設定が不足しています。")
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
    try:
        response = requests.post(url, headers=headers, data=json.dumps(body), timeout=10)
        if response.status_code == 200:
            print("LINE送信成功")
        else:
            print(f"LINE送信失敗: {response.status_code} {response.text}")
    except Exception as e:
        print(f"LINE通信エラー: {e}")

# ============================
# 共通ヘルパー
# ============================
def get_json(url: str):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        return resp.json()
    except:
        return {}

# ============================
# NEW: Fear & Greed Index 取得
# ============================
def fetch_fear_and_greed():
    try:
        # CNNのAPIエンドポイント（ブラウザのふりをして取得）
        url = "https://production.dataviz.cnn.io/index/feargreed/static/historical"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=10)
        data = resp.json()
        
        now_val = int(data['fear_and_greed']['score'])
        rating = data['fear_and_greed']['rating'].upper()
        
        # 日本語訳
        translations = {
            "EXTREME FEAR": "極度の恐怖",
            "FEAR": "恐怖",
            "NEUTRAL": "中立",
            "GREED": "強欲",
            "EXTREME GREED": "極度の強欲"
        }
        jp_rating = translations.get(rating, rating)
        return now_val, jp_rating
    except:
        return 0, "取得失敗"

# ============================
# VIX先物：多重化取得
# ============================
def fetch_vix_futures(vix_spot_price=0.0):
    # --- 1. Investing.com ---
    try:
        url = "https://www.investing.com/indices/us-spx-vix-futures"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        resp = requests.get(url, headers=headers, timeout=12)
        soup = BeautifulSoup(resp.text, "html.parser")
        p_el = soup.select_one('[data-test="instrument-price-last"]')
        c_el = soup.select_one('[data-test="instrument-price-change-percent"]')
        if p_el:
            p = float(p_el.text.replace(",", ""))
            c = float(c_el.text.replace("%", "").replace("(", "").replace(")", "").strip())
            return p, c
    except:
        pass

    # --- 2. CNBC API ---
    try:
        url = "https://quote.cnbc.com/quote-html-webservice/quote.htm?symbols=@VX.1&output=json"
        data = get_json(url)
        quote = data["QuickQuoteResult"]["QuickQuote"]
        return float(quote["last"]), float(quote["change_pct"])
    except:
        pass

    # --- 3. Fallback ---
    return vix_spot_price, 0.0

# ============================
# 市場データ集約
# ============================
def get_market_data():
    d = {"data_date": "不明"}
    targets = {
        "gold": "GC=F", "wti": "CL=F", "vix": "%5EVIX",
        "nq": "NQ=F", "nk": "NK=F", "es": "ES=F",
        "us10y": "%5ETNX", "us2y": "%5EIRX", "btc": "BTC-USD"
    }

    for key, symbol in targets.items():
        try:
            raw = get_json(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}")
            meta = raw["chart"]["result"][0]["meta"]
            p, prev = meta.get("regularMarketPrice"), meta.get("chartPreviousClose")
            if p and prev:
                d[f"{key}_price"], d[f"{key}_change"] = p, (p - prev) / prev * 100
                if key == "vix": d["data_date"] = datetime.fromtimestamp(meta["regularMarketTime"], timezone.utc).plus(timedelta(hours=9)).strftime("%Y.%m.%d") if "regularMarketTime" in meta else "不明"
        except:
            d[f"{key}_price"], d[f"{key}_change"] = 0.0, 0.0

    # 為替
    try:
        fx = get_json("https://api.frankfurter.app/latest?from=USD&to=JPY")
        d["usd_jpy"] = fx.get("rates", {}).get("JPY", 0.0)
    except:
        d["usd_jpy"] = 0.0

    # VIX先物 & Fear and Greed
    d["vxf_price"], d["vxf_change"] = fetch_vix_futures(vix_spot_price=d.get("vix_price", 0.0))
    d["fgi_score"], d["fgi_rating"] = fetch_fear_and_greed()
    d["yield_spread"] = d["us10y_price"] - d["us2y_price"] if d["us2y_price"] != 0 else 0.0

    return d

# ============================
# スコアロジック (変更なし)
# ============================
def calc_war_score(d):
    s = 0
    if d["vxf_change"] <= -7: s += 40
    elif d["vxf_change"] < 0: s += 20
    if d["vix_change"] <= -5: s += 25
    if d["us2y_change"] < 0: s += 20
    if d["yield_spread"] < 0: s += 20
    if d["btc_change"] >= 3: s += 15
    if d["nq_change"] > 0: s += 20
    if d["es_change"] > 0: s += 15
    return s

def calc_peace_score(d):
    s = 0
    if d["nq_change"] > 0: s += 35
    if d["es_change"] > 0: s += 35
    if d["us10y_change"] < 0: s += 20
    if d["usd_jpy"] >= 150: s += 20
    if d["btc_change"] > 0: s += 15
    return s

def calc_transition_score(d):
    s = 0
    if 15 < d["vix_price"] < 20:
        if d["vxf_change"] < 0: s += 25
        if d["nq_change"] > 0: s += 20
        if d["us10y_change"] < 0: s += 20
        if d["btc_change"] > 0: s += 15
    return s

def classify_zone(scaled, mode):
    if mode == "war":
        if scaled >= 80: return "反転確定ゾーン"
        if scaled >= 60: return "反転の可能性大"
        if scaled >= 40: return "反転の初期兆候"
        return "有事継続"
    if mode == "transition":
        if scaled >= 70: return "平時移行の可能性"
        if scaled >= 50: return "移行期の兆候"
        return "方向感なし"
    if scaled >= 80: return "強い上昇トレンド"
    if scaled >= 60: return "上昇トレンド"
    return "トレンド不明瞭"

# ============================
# メッセージ構築 (F&G Indexを追加)
# ============================
def build_message(d):
    vix_p = d["vix_price"]
    if vix_p >= 20:
        mode, max_score, zone_mode = "戦時モード：相場反転スコア", 155, "war"
        score = calc_war_score(d)
    elif vix_p <= 15:
        mode, max_score, zone_mode = "平時モード：トレンドスコア", 135, "peace"
        score = calc_peace_score(d)
    else:
        mode, max_score, zone_mode = "移行期モード：様子見", 140, "transition"
        score = calc_transition_score(d)

    scaled = min(max(int(score / max_score * 100), 0), 100)
    zone = classify_zone(scaled, zone_mode)
    today = datetime.now().strftime("%Y.%m.%d")

    msg = [
        f"【{today} {mode}（100点版）】",
        f"データ日：{d['data_date']}\n",
        f"▼ 投資家心理 (Fear & Greed Index)",
        f"指数：{d['fgi_score']} / 100（{d['fgi_rating']}）\n",
        f"▼ 主要指標",
        f"VIX現物: {d['vix_price']:.2f}（{d['vix_change']:.2f}%）",
        f"VIX先物: {d['vxf_price']:.2f}（{d['vxf_change']:.2f}%）\n",
        "▼ 金利・イールドカーブ",
        f"・米2年金利: {d['us2y_price']:.2f}（{d['us2y_change']:.2f}%）",
        f"・米10年金利: {d['us10y_price']:.2f}（{d['us10y_change']:.2f}%）",
        f"・イールドカーブ(10Y-2Y): {d['yield_spread']:.2f}\n",
        "▼ 株価指数",
        f"・NASDAQ先物: {d['nq_price']:.2f}（{d['nq_change']:.2f}%）",
        f"・日経先物　: {d['nk_price']:.2f}（{d['nk_change']:.2f}%）",
        f"・S&P500先物: {d['es_price']:.2f}（{d['es_change']:.2f}%）\n",
        "▼ 暗号資産",
        f"・BTC : {d['btc_price']:.2f}（{d['btc_change']:.2f}%）\n",
        f"総合スコア：{scaled}点（{zone}）",
        f"※ 生スコア：{score} / {max_score}"
    ]
    return "\n".join(msg)

def main():
    data = get_market_data()
    msg = build_message(data)
    send_line(msg)

if __name__ == "__main__":
    main()
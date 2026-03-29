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
    body = {"to": LINE_USER_ID, "messages": [{"type": "text", "text": text}]}
    try:
        response = requests.post(url, headers=headers, data=json.dumps(body), timeout=10)
        print(f"LINE送信結果: {response.status_code}")
    except Exception as e:
        print(f"LINE通信エラー: {e}")

# ============================
# NEW: Fear & Greed Index 取得（強化版）
# ============================
def fetch_fear_and_greed():
    try:
        # 複数のエンドポイントを試行
        urls = [
            "https://production.dataviz.cnn.io/index/feargreed/static/historical",
            "https://fear-and-greed-index.p.rapidapi.com/v1/fgi" # 予備（将来用）
        ]
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Referer": "https://www.cnn.com/markets/fear-and-greed"
        }
        resp = requests.get(urls[0], headers=headers, timeout=10)
        data = resp.json()
        
        now_val = int(data['fear_and_greed']['score'])
        rating = data['fear_and_greed']['rating'].upper()
        
        translations = {"EXTREME FEAR": "極度の恐怖", "FEAR": "恐怖", "NEUTRAL": "中立", "GREED": "強欲", "EXTREME GREED": "極度の強欲"}
        return now_val, translations.get(rating, rating)
    except Exception as e:
        print(f"F&G取得失敗: {e}")
        return 0, "取得失敗"

# ============================
# VIX現物・先物：取得強化
# ============================
def fetch_vix_spot():
    # Yahoo FinanceのVIX現物取得
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/^VIX" # エンコードなしを試行
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10).json()
        meta = resp["chart"]["result"][0]["meta"]
        p = float(meta["regularMarketPrice"])
        prev = float(meta["chartPreviousClose"])
        change = (p - prev) / prev * 100
        # データ日時の取得
        ts = meta.get("regularMarketTime")
        dt = (datetime.fromtimestamp(ts, timezone.utc) + timedelta(hours=9)).strftime("%Y.%m.%d") if ts else "不明"
        return p, change, dt
    except:
        return 0.0, 0.0, "不明"

def fetch_vix_futures(vix_spot_price=0.0):
    # CNBC API経由で先物を取得
    try:
        url = "https://quote.cnbc.com/quote-html-webservice/quote.htm?symbols=@VX.1&output=json"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10).json()
        quote = resp["QuickQuoteResult"]["QuickQuote"]
        return float(quote["last"]), float(quote["change_pct"])
    except:
        # ダメならInvesting.comをトライ
        try:
            url = "https://www.investing.com/indices/us-spx-vix-futures"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"}
            resp = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(resp.text, "html.parser")
            p_el = soup.select_one('[data-test="instrument-price-last"]')
            if p_el:
                return float(p_el.text.replace(",", "")), 0.0
        except:
            pass
    return vix_spot_price, 0.0 # 最終手段

# ============================
# メイン集約処理
# ============================
def get_market_data():
    d = {}
    # 1. VIX現物の取得
    d["vix_price"], d["vix_change"], d["data_date"] = fetch_vix_spot()
    
    # 2. VIX先物 & F&G
    d["vxf_price"], d["vxf_change"] = fetch_vix_futures(vix_spot_price=d["vix_price"])
    d["fgi_score"], d["fgi_rating"] = fetch_fear_and_greed()

    # 3. その他市場データ
    targets = {
        "gold": "GC=F", "wti": "CL=F", "nq": "NQ=F", "nk": "NK=F", 
        "es": "ES=F", "us10y": "^TNX", "us2y": "^IRX", "btc": "BTC-USD"
    }
    for key, symbol in targets.items():
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            raw = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
            meta = raw["chart"]["result"][0]["meta"]
            p = meta["regularMarketPrice"]
            prev = meta["chartPreviousClose"]
            d[f"{key}_price"], d[f"{key}_change"] = p, (p - prev) / prev * 100
        except:
            d[f"{key}_price"], d[f"{key}_change"] = 0.0, 0.0

    try:
        fx = requests.get("https://api.frankfurter.app/latest?from=USD&to=JPY", timeout=10).json()
        d["usd_jpy"] = fx["rates"]["JPY"]
    except:
        d["usd_jpy"] = 0.0

    d["yield_spread"] = d["us10y_price"] - d["us2y_price"] if d["us2y_price"] != 0 else 0.0
    return d

# ============================
# スコア・メッセージ（ロジックは不変）
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

def build_message(d):
    vix_p = d["vix_price"]
    if vix_p >= 20:
        mode, max_score, zone_mode = "戦時モード：相場反転スコア", 155, "war"
        score = calc_war_score(d)
    elif 0 < vix_p <= 15:
        mode, max_score, zone_mode = "平時モード：トレンドスコア", 135, "peace"
        score = calc_peace_score(d)
    else:
        mode, max_score, zone_mode = "移行期/データ異常モード", 140, "transition"
        score = calc_transition_score(d)

    scaled = min(max(int(score / max_score * 100), 0), 100) if max_score > 0 else 0
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
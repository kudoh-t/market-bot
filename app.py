import requests
import json
import os
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

# ============================
# 設定：環境変数
# ============================
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")

def send_line(text: str):
    if not LINE_ACCESS_TOKEN or not LINE_USER_ID: return
    url = "https://api.line.me/v2/bot/message/push"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {LINE_ACCESS_TOKEN}"}
    body = {"to": LINE_USER_ID, "messages": [{"type": "text", "text": text}]}
    try:
        requests.post(url, headers=headers, data=json.dumps(body), timeout=10)
    except:
        pass

# ============================
# Fear & Greed Index 取得
# ============================
def fetch_fear_and_greed():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Referer": "https://www.cnn.com/markets/fear-and-greed"
    }
    try:
        res = requests.get("https://production.dataviz.cnn.io/index/feargreed/static/feargreed", headers=headers, timeout=10).json()
        val = int(res['fgi']['now']['value'])
        txt = res['fgi']['now']['value_text'].upper()
        return val, txt
    except:
        try:
            res = requests.get("https://api.alternative.me/fng/?limit=1", timeout=10).json()
            val = int(res['data'][0]['value'])
            txt = res['data'][0]['value_classification'].upper()
            return val, txt
        except:
            return 0, "取得失敗"

# ============================
# VIX現物・先物 取得
# ============================
def fetch_vix_spot():
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX"
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
        m = res["chart"]["result"][0]["meta"]
        p, prev = m["regularMarketPrice"], m["chartPreviousClose"]
        dt = (datetime.fromtimestamp(m["regularMarketTime"], timezone.utc) + timedelta(hours=9)).strftime("%Y.%m.%d")
        return p, (p - prev) / prev * 100, dt
    except:
        return 0.0, 0.0, "不明"

def fetch_vix_futures(vix_spot):
    try:
        url = "https://www.investing.com/indices/us-spx-vix-futures"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        p_el = soup.select_one('[data-test="instrument-price-last"]')
        if p_el:
            return float(p_el.text.replace(",", "")), 0.0
    except:
        pass
    return vix_spot, 0.0

# ============================
# 市場データ集約
# ============================
def get_market_data():
    d = {}
    d["vix_price"], d["vix_change"], d["data_date"] = fetch_vix_spot()
    d["vxf_price"], d["vxf_change"] = fetch_vix_futures(d["vix_price"])
    fgi_val, fgi_txt = fetch_fear_and_greed()
    trans = {"EXTREME FEAR": "極度の恐怖", "FEAR": "恐怖", "NEUTRAL": "中立", "GREED": "強欲", "EXTREME GREED": "極度の強欲"}
    d["fgi_score"], d["fgi_rating"] = fgi_val, trans.get(fgi_txt, fgi_txt)

    targets = {
        "gold": "GC=F", "wti": "CL=F", "nq": "NQ=F", "nk": "NK=F", 
        "es": "ES=F", "us10y": "%5ETNX", "us2y": "%5EIRX", "btc": "BTC-USD"
    }
    for k, s in targets.items():
        try:
            r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{s}", headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
            m = r["chart"]["result"][0]["meta"]
            p, pr = m["regularMarketPrice"], m["chartPreviousClose"]
            d[f"{k}_price"], d[f"{k}_change"] = p, (p - pr) / pr * 100
        except:
            d[f"{k}_price"], d[f"{k}_change"] = 0.0, 0.0

    try:
        fx = requests.get("https://api.frankfurter.app/latest?from=USD&to=JPY", timeout=10).json()
        d["usd_jpy"] = fx["rates"]["JPY"]
    except:
        d["usd_jpy"] = 0.0
    d["yield_spread"] = d["us10y_price"] - d["us2y_price"]
    return d

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

def build_message(d):
    vix_p = d["vix_price"]
    mode, max_score = ("戦時モード：相場反転スコア", 155) if vix_p >= 20 else ("平時モード：トレンドスコア", 135)
    score = calc_war_score(d) if vix_p >= 20 else 0 
    scaled = min(max(int(score / max_score * 100), 0), 100)
    
    msg = [
        f"【{datetime.now().strftime('%Y.%m.%d')} {mode}】",
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
        "▼ 商品（コモディティ）",
        f"・ゴールド : {d['gold_price']:.2f}（{d['gold_change']:.2f}%）",
        f"・WTI原油  : {d['wti_price']:.2f}（{d['wti_change']:.2f}%）\n",
        "▼ 株価指数",
        f"・NASDAQ先物: {d['nq_price']:.2f}（{d['nq_change']:.2f}%）",
        f"・日経先物　: {d['nk_price']:.2f}（{d['nk_change']:.2f}%）",
        f"・S&P500先物: {d['es_price']:.2f}（{d['es_change']:.2f}%）\n",
        "▼ 暗号資産",
        f"・BTC : {d['btc_price']:.2f}（{d['btc_change']:.2f}%）\n",
        f"総合スコア：{scaled}点",
        f"※ 生スコア：{score} / {max_score}"
    ]
    return "\n".join(msg)

def main():
    data = get_market_data()
    send_line(build_message(data))

if __name__ == "__main__":
    main()
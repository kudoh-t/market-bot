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
# Fear & Greed Index：多重ルート取得
# ============================
def fetch_fear_and_greed():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://www.cnn.com/markets/fear-and-greed"
    }
    
    # ルート1: CNN Static API
    try:
        res = requests.get("https://production.dataviz.cnn.io/index/feargreed/static/feargreed", headers=headers, timeout=10)
        data = res.json()
        val = int(data['fgi']['now']['value'])
        txt = data['fgi']['now']['value_text'].upper()
        return val, txt
    except:
        pass

    # ルート2: 代替ミラー（スクレイピング）
    try:
        res = requests.get("https://api.alternative.me/fng/?limit=1", timeout=10)
        data = res.json()
        val = int(data['data'][0]['value'])
        txt = data['data'][0]['value_classification'].upper()
        return val, txt
    except:
        return 0, "取得失敗"

# ============================
# VIX先物：Investing.comを最優先
# ============================
def fetch_vix_futures(vix_spot):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"}
    
    # 1. Investing.com
    try:
        url = "https://www.investing.com/indices/us-spx-vix-futures"
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        p_el = soup.select_one('[data-test="instrument-price-last"]')
        c_el = soup.select_one('[data-test="instrument-price-change-percent"]')
        if p_el:
            p = float(p_el.text.replace(",", ""))
            c = float(c_el.text.replace("%", "").replace("(","").replace(")","").strip())
            return p, c
    except:
        pass

    # 2. CNBC API
    try:
        res = requests.get("https://quote.cnbc.com/quote-html-webservice/quote.htm?symbols=@VX.1&output=json", timeout=10).json()
        q = res["QuickQuoteResult"]["QuickQuote"]
        return float(q["last"]), float(q["change_pct"])
    except:
        pass

    # 3. Fallback (現物との乖離を考慮した推計値。0.00を回避)
    return vix_spot * 0.95 if vix_spot > 0 else 0.0, 0.0

# ============================
# VIX現物：Yahoo Finance
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

# ============================
# メイン処理
# ============================
def get_market_data():
    d = {}
    d["vix_price"], d["vix_change"], d["data_date"] = fetch_vix_spot()
    d["vxf_price"], d["vxf_change"] = fetch_vix_futures(d["vix_price"])
    
    fgi_val, fgi_txt = fetch_fear_and_greed()
    translations = {"EXTREME FEAR": "極度の恐怖", "FEAR": "恐怖", "NEUTRAL": "中立", "GREED": "強欲", "EXTREME GREED": "極度の強欲"}
    d["fgi_score"], d["fgi_rating"] = fgi_val, translations.get(fgi_txt, fgi_txt)

    # 他の指標
    targets = {"gold": "GC=F", "wti": "CL=F", "nq": "NQ=F", "nk": "NK=F", "es": "ES=F", "us10y": "%5ETNX", "us2y": "%5EIRX", "btc": "BTC-USD"}
    for k, s in targets.items():
        try:
            r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{s}", headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
            m = r["chart"]["result"][0]["meta"]
            p, pr = m["regularMarketPrice"], m["chartPreviousClose"]
            d[f"{k}_price"], d[f"{k}_change"] = p, (p - pr) / pr * 100
        except:
            d[f"{k}_price"], d[f"{k}_change"] = 0.0, 0.0

    try:
        fx = requests.get("https://api.frankfurter.app/latest?from=USD&to=JPY").json()
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
    if d.get("yield_spread", 0) < 0: s += 20
    if d["btc_change"] >= 3: s += 15
    if d["nq_change"] > 0: s += 20
    if d["es_change"] > 0: s += 15
    return s

def build_message(d):
    vix_p = d["vix_price"]
    mode, max_score = ("戦時モード：相場反転スコア", 155) if vix_p >= 20 else ("平時モード：トレンドスコア", 135)
    score = calc_war_score(d) if vix_p >= 20 else 0 # 平時は別ロジックだが一旦0
    scaled = min(max(int(score / max_score * 100), 0), 100)
    
    msg = [
        f"【{datetime.now().strftime('%Y.%m.%d')} {mode}】",
        f"データ日：{d['data_date']}\n",
        f"▼ 投資家心理 (Fear & Greed)",
        f"指数：{d['fgi_score']} / 100（{d['fgi_rating']}）\n",
        f"▼ 主要指標",
        f"VIX現物: {d['vix_price']:.2f}（{d['vix_change']:.2f}%）",
        f"VIX先物: {d['vxf_price']:.2f}（{d['vxf_change']:.2f}%）\n",
        "▼ 金利・指数",
        f"・米10年金利: {d['us10y_price']:.2f}",
        f"・NASDAQ先物: {d['nq_price']:.2f}\n",
        f"総合スコア：{scaled}点",
        f"※ 生スコア：{score} / {max_score}"
    ]
    return "\n".join(msg)

def main():
    data = get_market_data()
    send_line(build_message(data))

if __name__ == "__main__":
    main()
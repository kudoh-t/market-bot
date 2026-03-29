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
    if not LINE_ACCESS_TOKEN or not LINE_USER_ID:
        print("LINE設定が不足しています。")
        return
    url = "https://api.line.me/v2/bot/message/push"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {LINE_ACCESS_TOKEN}"}
    body = {"to": LINE_USER_ID, "messages": [{"type": "text", "text": text}]}
    try:
        response = requests.post(url, headers=headers, data=json.dumps(body), timeout=10)
        print(f"LINE送信結果: {response.status_code}")
    except Exception as e:
        print(f"LINE通信エラー: {e}")

# ============================
# Fear & Greed Index 取得（二段構え）
# ============================
def fetch_fear_and_greed():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Referer": "https://www.cnn.com/markets/fear-and-greed"
    }
    # ルート1: CNN API
    try:
        res = requests.get("https://production.dataviz.cnn.io/index/feargreed/static/feargreed", headers=headers, timeout=10)
        data = res.json()
        val = int(data['fgi']['now']['value'])
        txt = data['fgi']['now']['value_text'].upper()
        return val, txt
    except:
        # ルート2: Alternative API (CNNが落ちている時のバックアップ)
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
        # ^VIX 現物取得
        url = "https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX"
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
        m = res["chart"]["result"][0]["meta"]
        p = float(m["regularMarketPrice"])
        prev = float(m["chartPreviousClose"])
        # 日本時間に変換
        dt = (datetime.fromtimestamp(m["regularMarketTime"], timezone.utc) + timedelta(hours=9)).strftime("%Y.%m.%d")
        return p, (p - prev) / prev * 100, dt
    except:
        return 0.0, 0.0, "不明"

def fetch_vix_futures(vix_spot):
    # Investing.com から先物を取得試行
    try:
        url = "https://www.investing.com/indices/us-spx-vix-futures"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        p_el = soup.select_one('[data-test="instrument-price-last"]')
        c_el = soup.select_one('[data-test="instrument-price-change-percent"]')
        if p_el:
            p = float(p_el.text.replace(",", ""))
            c_txt = c_el.text.replace("%", "").replace("(","").replace(")","").strip()
            return p, float(c_txt)
    except:
        pass
    # 失敗時は現物を代用して計算の破綻を防ぐ
    return vix_spot, 0.0

# ============================
# 市場データ集約
# ============================
def get_market_data():
    d = {}
    # VIX & Fear & Greed
    d["vix_price"], d["vix_change"], d["data_date"] = fetch_vix_spot()
    d["vxf_price"], d["vxf_change"] = fetch_vix_futures(d["vix_price"])
    fgi_val, fgi_txt = fetch_fear_and_greed()
    
    trans = {"EXTREME FEAR": "極度の恐怖", "FEAR": "恐怖", "NEUTRAL": "中立", "GREED": "強欲", "EXTREME GREED": "極度の強欲"}
    d["fgi_score"], d["fgi_rating"] = fgi_val, trans.get(fgi_txt, fgi_txt)

    # 各種市場データ (Yahoo Finance)
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

    # 為替 & イールドカーブ計算
    try:
        fx = requests.get("https://api.frankfurter.app/latest?from=USD&to=JPY", timeout=10).json()
        d["usd_jpy"] = fx["rates"]["JPY"]
    except:
        d["usd_jpy"] = 0.0
    d["yield_spread"] = d["us10y_price"] - d["us2y_price"]
    
    return d

# ============================
# スコア計算ロジック
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

def classify_zone(scaled):
    if scaled >= 80: return "反転確定ゾーン"
    if scaled >= 60: return "反転の可能性大"
    if scaled >= 40: return "反転の初期兆候"
    return "有事継続"

# ============================
# LINEメッセージ構築
# ============================
def build_message(d):
    vix_p = d["vix_price"]
    # モード判定
    if vix_p >= 20:
        mode, max_score = "戦時モード：相場反転スコア", 155
        score = calc_war_score(d)
    else:
        mode, max_score = "平時モード：トレンドスコア", 135
        score = 0 # 平時用ロジックは必要に応じて後日拡張
        
    scaled = min(max(int(score / max_score * 100), 0), 100) if max_score > 0 else 0
    zone = classify_zone(scaled)
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

# ============================
# 実行
# ============================
def main():
    data = get_market_data()
    message = build_message(data)
    send_line(message)

if __name__ == "__main__":
    main()
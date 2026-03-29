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
# データ取得系関数
# ============================
def fetch_fear_and_greed():
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.cnn.com/markets/fear-and-greed"}
    try:
        res = requests.get("https://production.dataviz.cnn.io/index/feargreed/static/feargreed", headers=headers, timeout=10).json()
        return int(res['fgi']['now']['value']), res['fgi']['now']['value_text'].upper()
    except:
        try:
            res = requests.get("https://api.alternative.me/fng/?limit=1", timeout=10).json()
            return int(res['data'][0]['value']), res['data'][0]['value_classification'].upper()
        except:
            return 0, "取得失敗"

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
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        p_el = soup.select_one('[data-test="instrument-price-last"]')
        if p_el: return float(p_el.text.replace(",", "")), 0.0
    except: pass
    return vix_spot, 0.0

# ============================
# マーケット一言診断ロジック
# ============================
def analyze_market(d):
    analysis = []
    
    # 1. VIX乖離（バックワーデーション）
    if d["vix_price"] > d["vxf_price"] + 0.5:
        analysis.append("⚠️VIX逆転：現物が先物を上回る異常事態（パニック）です。歴史的には底打ちが近いサイン。")
    elif d["vix_price"] < d["vxf_price"] - 1.0:
        analysis.append("✅VIX順鞘：市場は冷静さを取り戻しつつあります。平時への移行フェーズです。")

    # 2. 金利と指数の相関
    if d["us10y_change"] > 1.0 and d["nq_change"] < -0.5:
        analysis.append("📉金利上昇の重力：米10年金利の上昇がNASDAQの重石となっています。テック株には逆風。")
    elif d["us10y_change"] < -1.0 and d["nq_change"] < -1.0:
        analysis.append("😨景気後退懸念：金利低下と株安が同時進行。市場はインフレより『不況』を恐れ始めています。")

    # 3. NASDAQと日経平均の乖離
    diff_nk_nq = d["nk_change"] - d["nq_change"]
    if diff_nk_nq > 1.5:
        analysis.append("🇯🇵日経独歩高：米国株に比べ日本株が過剰に買われています。円安恩恵か、一時的な資金逃避先か。")
    elif diff_nk_nq < -1.5:
        analysis.append("🏯日本株の不振：米国株の底堅さに比べ、日本株が軟調。独自の売り要因（政治・為替）を警戒。")

    # 4. BTCの先行性
    if d["btc_change"] < -3.0:
        analysis.append("🕊️カナリアの沈黙：BTCの急落はリスク資産全般からの資金引き揚げの先行指標となる可能性あり。")

    if not analysis:
        analysis.append("🧐特筆すべき歪みなし：各指標は概ね相関通りに動いています。トレンド追随が基本です。")
    
    return "\n".join(analysis[:3]) # 最大3つまで表示

# ============================
# メイン処理
# ============================
def get_market_data():
    d = {}
    d["vix_price"], d["vix_change"], d["data_date"] = fetch_vix_spot()
    d["vxf_price"], d["vxf_change"] = fetch_vix_futures(d["vix_price"])
    d["fgi_score"], fgi_txt = fetch_fear_and_greed()
    trans = {"EXTREME FEAR": "極度の恐怖", "FEAR": "恐怖", "NEUTRAL": "中立", "GREED": "強欲", "EXTREME GREED": "極度の強欲"}
    d["fgi_rating"] = trans.get(fgi_txt, fgi_txt)

    targets = {"gold": "GC=F", "wti": "CL=F", "nq": "NQ=F", "nk": "NK=F", "es": "ES=F", "us10y": "%5ETNX", "us2y": "%5EIRX", "btc": "BTC-USD"}
    for k, s in targets.items():
        try:
            r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{s}", headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
            m = r["chart"]["result"][0]["meta"]
            d[f"{k}_price"], d[f"{k}_change"] = m["regularMarketPrice"], (m["regularMarketPrice"] - m["chartPreviousClose"]) / m["chartPreviousClose"] * 100
        except: d[f"{k}_price"], d[f"{k}_change"] = 0.0, 0.0

    d["yield_spread"] = d["us10y_price"] - d["us2y_price"]
    return d

def build_message(d):
    vix_p = d["vix_price"]
    mode, max_s = ("戦時モード：相場反転スコア", 155) if vix_p >= 20 else ("平時モード：トレンドスコア", 135)
    
    score = 0
    if vix_p >= 20: # 戦時ロジック
        if d["vxf_change"] <= -7: score += 40
        elif d["vxf_change"] < 0: score += 20
        if d["vix_change"] <= -5: score += 25
        if d["us2y_change"] < 0: score += 20
        if d["yield_spread"] < 0: score += 20
        if d["btc_change"] >= 3: score += 15
        if d["nq_change"] > 0: score += 20
        if d["es_change"] > 0: score += 15

    scaled = min(max(int(score / max_s * 100), 0), 100)
    diagnosis = analyze_market(d)
    
    msg = [
        f"【{datetime.now().strftime('%Y.%m.%d')} {mode}】",
        f"📅 データ日：{d['data_date']}\n",
        f"▼ 投資家心理 (Fear & Greed Index)",
        f"指数：{d['fgi_score']} / 100（{d['fgi_rating']}）\n",
        f"▼ 主要指標",
        f"VIX現物: {d['vix_price']:.2f}（{d['vix_change']:.2f}%）",
        f"VIX先物: {d['vxf_price']:.2f}（{d['vxf_change']:.2f}%）\n",
        "▼ 金利・イールドカーブ",
        f"・米2年金利: {d['us2y_price']:.2f}（{d['us2y_change']:.2f}%）",
        f"・米10年金利: {d['us10y_price']:.2f}（{d['us10y_change']:.2f}%）",
        f"・イールドカーブ: {d['yield_spread']:.2f}\n",
        "▼ 商品（コモディティ）",
        f"・ゴールド : {d['gold_price']:.2f}（{d['gold_change']:.2f}%）",
        f"・WTI原油  : {d['wti_price']:.2f}（{d['wti_change']:.2f}%）\n",
        "▼ 株価指数",
        f"・NASDAQ先物: {d['nq_price']:.2f}（{d['nq_change']:.2f}%）",
        f"・日経平均先物: {d['nk_price']:.2f}（{d['nk_change']:.2f}%）\n",
        "▼ 暗号資産",
        f"・BTC : {d['btc_price']:.2f}（{d['btc_change']:.2f}%）\n",
        f"総合反転スコア：{scaled}点",
        f"\n🤖 マーケット一言診断：\n{diagnosis}"
    ]
    return "\n".join(msg)

def main():
    data = get_market_data()
    send_line(build_message(data))

if __name__ == "__main__": main()
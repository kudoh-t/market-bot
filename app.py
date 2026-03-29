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
    except: pass

# ============================
# 判定・解説ロジック
# ============================
def get_fgi_detail(val):
    if val <= 25:   return f"🔥指数({val}): 極度の恐怖。歴史的には絶好の仕込み時。少額ずつ買い向かう勇気が報われやすい時期です。"
    elif val <= 45: return f"😨指数({val}): 恐怖。下落への警戒が強い状態。リバウンドを待つか、キャッシュ比率を維持して静観が吉。"
    elif val <= 55: return f"😐指数({val}): 中立。強弱感が拮抗。トレンドが明確になるまで大きな勝負は避けるべきです。"
    elif val <= 75: return f"🚀指数({val}): 強欲。過熱感あり。追撃買いは控え、利益確定を優先的に検討すべきフェーズ。"
    else:           return f"🚨指数({val}): 極度の強欲。バブル的な動き。いつ急落が来てもおかしくない警戒最大の状態。"

def analyze_market_action(d):
    actions = []
    # 1. VIXバックワーデーション判定
    if d["vix_price"] > d["vxf_price"] + 0.5:
        actions.append("⚠️【パニック発生】現物VIXが先物より高い異常事態。短期的な底打ちが近いシグナルです。狼狽売りに乗らず反転を待ちましょう。")
    # 2. 金利とNASDAQの相関
    if d["us10y_change"] > 1.2 and d["nq_change"] < -0.8:
        actions.append("📉【重力注意】米金利の急騰が株価を押し下げています。ハイテク株の買い増しは金利が落ち着くまで待機が安全。")
    # 3. 日米の乖離
    diff = d["nk_change"] - d["nq_change"]
    if diff > 2.0:  actions.append("🇯🇵【日本株独歩高】米株より日本株が強すぎます。円安の限界や米株への追随リスクを考え、一部利確も一手。")
    elif diff < -2.0: actions.append("🏯【日本株出遅れ】米株に比べ日本株が売られすぎです。独自の売り要因がなければ、日本株の拾い場。")
    # 4. BTCの先行性
    if d["btc_change"] < -4.0:
        actions.append("🕊️【先行指標赤信号】BTC急落。リスクマネーが逃げ始めています。今夜の米株市場での急落に備え、警戒を。")
    
    return "\n\n".join(actions[:2]) if actions else "🧐【静観】目立った歪みはありません。現在のポジションを維持しつつトレンド待ちです。"

# ============================
# データ取得系
# ============================
def fetch_vix_spot():
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX"
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
        m = res["chart"]["result"][0]["meta"]
        p, pr = m["regularMarketPrice"], m["chartPreviousClose"]
        dt = (datetime.fromtimestamp(m["regularMarketTime"], timezone.utc) + timedelta(hours=9)).strftime("%Y.%m.%d")
        return p, (p - pr) / pr * 100, dt
    except: return 0.0, 0.0, "不明"

def fetch_vix_futures(vix_spot):
    try:
        res = requests.get("https://www.investing.com/indices/us-spx-vix-futures", headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        p = float(BeautifulSoup(res.text, "html.parser").select_one('[data-test="instrument-price-last"]').text.replace(",", ""))
        return p, 0.0
    except: return vix_spot, 0.0 # 失敗時は現物で補完

def get_market_data():
    d = {}
    d["vix_price"], d["vix_change"], d["data_date"] = fetch_vix_spot()
    d["vxf_price"], d["vxf_change"] = fetch_vix_futures(d["vix_price"])
    
    # Fear & Greed 取得
    try:
        f_res = requests.get("https://production.dataviz.cnn.io/index/feargreed/static/feargreed", headers={"User-Agent":"Mozilla/5.0"}, timeout=10).json()
        d["fgi_score"] = int(f_res['fgi']['now']['value'])
    except:
        try:
            f_res = requests.get("https://api.alternative.me/fng/?limit=1", timeout=10).json()
            d["fgi_score"] = int(f_res['data'][0]['value'])
        except: d["fgi_score"] = 0
    d["fgi_text"] = get_fgi_detail(d["fgi_score"])

    # 全指標一括取得 (重複を避けるためのループ)
    targets = {"gold": "GC=F", "wti": "CL=F", "nq": "NQ=F", "nk": "NK=F", "es": "ES=F", "us10y": "%5ETNX", "us2y": "%5EIRX", "btc": "BTC-USD"}
    for k, s in targets.items():
        try:
            r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{s}", headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
            m = r["chart"]["result"][0]["meta"]
            d[f"{k}_price"], d[f"{k}_change"] = m["regularMarketPrice"], (m["regularMarketPrice"] - m["chartPreviousClose"]) / m["chartPreviousClose"] * 100
        except: d[f"{k}_price"], d[f"{k}_change"] = 0.0, 0.0

    d["yield_spread"] = d["us10y_price"] - d["us2y_price"]
    return d

# ============================
# メッセージ構築・実行
# ============================
def build_message(d):
    vix_p = d["vix_price"]
    mode, max_s = ("戦時：反転スコア", 155) if vix_p >= 20 else ("平時：トレンド", 135)
    
    score = 0
    if vix_p >= 20: # 有事の際の反転スコア加算
        if d["vix_change"] <= -5: score += 25
        if d["us2y_change"] < 0: score += 20
        if d["yield_spread"] < 0: score += 20
        if d["btc_change"] >= 3: score += 15
        if d["nq_change"] > 0: score += 20
        if d["es_change"] > 0: score += 15

    scaled = min(max(int(score / max_s * 100), 0), 100)
    
    msg = [
        f"【{datetime.now().strftime('%Y.%m.%d')} {mode}】",
        f"📅 データ日：{d['data_date']}\n",
        f"▼ 投資家心理 (Fear & Greed Index)",
        f"{d['fgi_text']}\n",
        f"▼ 主要指標",
        f"VIX現物: {d['vix_price']:.2f}（{d['vix_change']:.2f}%）",
        f"VIX先物: {d['vxf_price']:.2f}\n",
        "▼ 商品・金利・暗号資産",
        f"・Gold: {d['gold_price']:.1f} / 原油: {d['wti_price']:.1f}",
        f"・米10年金利: {d['us10y_price']:.2f} / BTC: {d['btc_price']:.0f}",
        f"・米2年金利: {d['us2y_price']:.2f}（{d['us2y_change']:.2f}%）\n",
        "▼ 株価指数",
        f"・NASDAQ先物: {d['nq_price']:.1f}（{d['nq_change']:.2f}%）",
        f"・日経平均先物: {d['nk_price']:.1f}（{d['nk_change']:.2f}%）",
        f"・S&P500先物: {d['es_price']:.1f}（{d['es_change']:.2f}%）\n",
        f"反転期待度：{scaled}点",
        f"--------------------------",
        f"💡 【行動指針】\n{analyze_market_action(d)}"
    ]
    return "\n".join(msg)

def main():
    data = get_market_data()
    send_line(build_message(data))

if __name__ == "__main__": main()
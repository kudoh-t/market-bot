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
    elif val <= 55: return f"😐指数({val}): 中立。強弱感が拮抗。トレンドが明確になるまで大きな勝負は避けるべき。"
    elif val <= 75: return f"🚀指数({val}): 強欲。過熱感あり。追撃買いは控え、利益確定を優先的に検討すべきフェーズ。"
    else:           return f"🚨指数({val}): 極度の強欲。バブル的な動き。いつ急落が来てもおかしくない警戒最大の状態。"

def get_yield_comment(spread):
    if spread < -0.5:
        return "⚠️強い逆イールド：景気後退への強い警戒。利上げの限界と将来の不況を市場が確信しています。"
    elif spread < 0:
        return "🧐逆イールド状態：異常な金利体系。景気サイクルの終盤で、相場の転換点が近づいているサインです。"
    elif 0 <= spread < 0.2:
        return "🔄フラット化/解消直後：逆イールド解消は「利下げ開始」の予兆。過去、暴落や急反発が起きやすい転換点です。"
    else:
        return "✅順イールド：正常な金利体系。長期的な景気拡大への期待が反映されています。"

def get_score_comment(scaled):
    if scaled >= 80: return "💎【反転確定ゾーン】複数の反転シグナルが点灯。反発のエネルギーが極めて高く、攻めに転じる好機です。"
    if scaled >= 50: return "📈【反転の兆し】売り圧力が和らぎ、買い戻しの動きが見え始めました。打診買いを検討できる圏内です。"
    if scaled >= 30: return "⚠️【反転の初期兆候】一部に下げ止まりの動きがありますが、まだ不安定。慎重な見極めが必要です。"
    return "🌑【有事継続】下落トレンドが強く、反転の根拠が不足しています。無理な逆張りは避け、キャッシュを保護すべき局面です。"

def analyze_market_action(d):
    actions = []
    if d["vix_price"] > d["vxf_price"] + 0.5:
        actions.append("⚠️【パニック発生】現物VIXが先物より高い異常事態。パニック売りに乗らず反転を待ちましょう。")
    if d["us10y_change"] > 1.2 and d["nq_change"] < -0.8:
        actions.append("📉【重力注意】米金利の急騰が株価を押し下げ。ハイテク株の買い増しは金利沈静化まで待機。")
    diff = d["nk_change"] - d["nq_change"]
    if diff > 2.0:  actions.append("🇯🇵【日本株独歩高】米株より強すぎ。追随リスクを考え、一部利確も一手。")
    elif diff < -2.0: actions.append("🏯【日本株出遅れ】米株に比べ売られすぎ。独自の売り要因がなければ拾い場か。")
    if d["btc_change"] < -4.0:
        actions.append("🕊️【先行指標赤信号】BTC急落。リスクマネー流出のサイン。今夜の米株市場に警戒を。")
    return "\n\n".join(actions[:2]) if actions else "🧐【特筆事項なし】目立った歪みはありません。現在のポジションを維持しトレンド待ち。"

# ============================
# データ取得系
# ============================
def fetch_vix_spot():
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX"
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
        r = res["chart"]["result"][0]["meta"]
        p, pr = r["regularMarketPrice"], r["chartPreviousClose"]
        dt = (datetime.fromtimestamp(r["regularMarketTime"], timezone.utc) + timedelta(hours=9)).strftime("%Y.%m.%d")
        return p, (p - pr) / pr * 100, dt
    except: return 0.0, 0.0, "不明"

def fetch_vix_futures(vix_spot):
    try:
        res = requests.get("https://www.investing.com/indices/us-spx-vix-futures", headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        p = float(BeautifulSoup(res.text, "html.parser").select_one('[data-test="instrument-price-last"]').text.replace(",", ""))
        return p, 0.0
    except: return vix_spot, 0.0

def get_market_data():
    d = {}
    d["vix_price"], d["vix_change"], d["data_date"] = fetch_vix_spot()
    d["vxf_price"], d["vxf_change"] = fetch_vix_futures(d["vix_price"])
    try:
        f_res = requests.get("https://production.dataviz.cnn.io/index/feargreed/static/feargreed", headers={"User-Agent":"Mozilla/5.0"}, timeout=10).json()
        d["fgi_score"] = int(f_res['fgi']['now']['value'])
    except:
        try:
            f_res = requests.get("https://api.alternative.me/fng/?limit=1", timeout=10).json()
            d["fgi_score"] = int(f_res['data'][0]['value'])
        except: d["fgi_score"] = 0
    d["fgi_text"] = get_fgi_detail(d["fgi_score"])

    targets = {"gold": "GC=F", "wti": "CL=F", "nq": "NQ=F", "nk": "NK=F", "es": "ES=F", "us10y": "%5ETNX", "us2y": "%5EIRX", "btc": "BTC-USD"}
    for k, s in targets.items():
        try:
            r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{s}", headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
            m = r["chart"]["result"][0]["meta"]
            d[f"{k}_price"], d[f"{k}_change"] = m["regularMarketPrice"], (m["regularMarketPrice"] - m["chartPreviousClose"]) / m["chartPreviousClose"] * 100
        except: d[f"{k}_price"], d[f"{k}_change"] = 0.0, 0.0
    
    d["yield_spread"] = d["us10y_price"] - d["us2y_price"] # 修正: 10Y - 2Y
    d["yield_text"] = get_yield_comment(d["yield_spread"])
    return d

# ============================
# メッセージ構築
# ============================
def build_message(d):
    vix_p = d["vix_price"]
    mode, max_s = ("戦時モード：総合反転スコア", 155) if vix_p >= 20 else ("平時モード：トレンドスコア", 135)
    
    score = 0
    if vix_p >= 20:
        if d["vxf_change"] <= -7: score += 40
        elif d["vxf_change"] < 0: score += 20
        if d["vix_change"] <= -5: score += 25
        if d["us2y_change"] < 0: score += 20
        if d["yield_spread"] < 0: score += 20 # 逆イールド時に加点
        if d["btc_change"] >= 3: score += 15
        if d["nq_change"] > 0: score += 20
        if d["es_change"] > 0: score += 15

    scaled = min(max(int(score / max_s * 100), 0), 100)
    
    msg = [
        f"【{datetime.now().strftime('%Y.%m.%d')} {mode}】",
        f"📅 データ日：{d['data_date']}\n",
        f"▼ 投資家心理 (Fear & Greed Index)",
        f"{d['fgi_text']}\n",
        f"▼ 主要リスク指標",
        f"VIX現物: {d['vix_price']:.2f}（{d['vix_change']:.2f}%）",
        f"VIX先物: {d['vxf_price']:.2f}\n",
        "▼ 金利・イールドカーブ",
        f"・米2年金利 : {d['us2y_price']:.2f}（{d['us2y_change']:.2f}%）",
        f"・米10年金利: {d['us10y_price']:.2f}（{d['us10y_change']:.2f}%）",
        f"・金利差(10Y-2Y): {d['yield_spread']:.3f}",
        f"   💡{d['yield_text']}\n",
        "▼ 商品（コモディティ）",
        f"・ゴールド : {d['gold_price']:.1f}（{d['gold_change']:.2f}%）",
        f"・WTI原油  : {d['wti_price']:.1f}（{d['wti_change']:.2f}%）\n",
        "▼ 暗号資産",
        f"・BTC : ${d['btc_price']:.0f}（{d['btc_change']:.2f}%）\n",
        "▼ 株価指数",
        f"・NASDAQ先物: {d['nq_price']:.1f}（{d['nq_change']:.2f}%）",
        f"・日経平均先物: {d['nk_price']:.1f}（{d['nk_change']:.2f}%）",
        f"・S&P500先物 : {d['es_price']:.1f}（{d['es_change']:.2f}%）\n",
        f"⚖️ スコア評価：{scaled}点 / 100",
        f"（生スコア: {score} / {max_s}）",
        f"{get_score_comment(scaled)}\n",
        f"--------------------------",
        f"💡 【行動指針】\n{analyze_market_action(d)}"
    ]
    return "\n".join(msg)

def main():
    data = get_market_data()
    send_line(build_message(data))

if __name__ == "__main__": main()
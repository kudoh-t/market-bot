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
def get_vix_analysis(v_spot, v_fut, is_estimated):
    if is_estimated:
        return "⚠️先物データ取得不可：現物のみで診断中。先物との乖離判定をスキップします。"
    
    diff = v_spot - v_fut
    if diff > 0.5:
        return f"🚨異常乖離(逆転)：現物が先物を{diff:.2f}上回るパニック状態。歴史的に底打ちが近いサインです。"
    elif diff < -1.0:
        return f"✅正常乖離(順鞘)：先物の方が高い正常な状態。市場のパニックは落ち着いています。"
    else:
        return "😐均衡状態：現物と先物が同水準。方向感を模索中です。"

def get_fgi_detail(val):
    if val <= 25:   return f"🔥指数({val}): 極度の恐怖。総悲観ですが、歴史的には絶好の仕込み時です。"
    elif val <= 45: return f"😨指数({val}): 恐怖。下落への警戒が強い状態。静観が吉。"
    elif val <= 55: return f"😐指数({val}): 中立。強弱感が拮抗。トレンド待ち。"
    elif val <= 75: return f"🚀指数({val}): 強欲。過熱感あり。利益確定を優先。"
    else:           return f"🚨指数({val}): 極度の強欲。急落が来てもおかしくない警戒状態。"

def get_yield_comment(spread, us10y_change):
    if spread < 0:
        return "⚠️逆イールド状態：異常な金利体系。景気後退の強力な予兆です。"
    elif spread >= 0.5 and us10y_change > 0:
        return "⚡急激なスティープニング：長期金利急騰による順イールド化。債券売りへの警戒が必要です。"
    elif 0 <= spread < 0.2:
        return "🔄フラット化/解消直後：利下げ期待なら反転の兆し。金利上昇によるものなら株には逆風。"
    else:
        return "✅順イールド：金利体系は正常。ただし金利の『上昇速度』に注意。"

def get_score_comment(scaled):
    if scaled >= 80: return "💎【反転確定ゾーン】複数の反転シグナル点灯。攻めに転じる好機です。"
    if scaled >= 50: return "📈【反転の兆し】買い戻しの動き。打診買い検討圏内です。"
    if scaled >= 30: return "⚠️【初期兆候】一部下げ止まりですが、まだ不安定。慎重に。"
    return "🌑【有事継続】無理な逆張りは避け、キャッシュ保護を優先すべき局面です。"

def analyze_market_action(d):
    actions = []
    if not d["vxf_is_estimated"] and d["vix_price"] > d["vxf_price"] + 0.5:
        actions.append("⚠️【パニック/VIX逆転】現物VIXが先物より高い異常事態。パニック売りに乗らず反転を待ちましょう。")
    if d["us10y_change"] > 1.2 and d["nq_change"] < -0.8:
        actions.append("📉【金利の重力】長期金利の急騰が株価を押し下げ。不用意な買い増しは危険。")
    if d["gold_change"] > 2.0 and d["wti_change"] > 3.0:
        actions.append("🛢️【有事の動き】金と原油の同時急騰は地政学リスクを示唆。株には強い逆風です。")
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
        return p, False
    except: return vix_spot, True

def get_market_data():
    d = {}
    d["vix_price"], d["vix_change"], d["data_date"] = fetch_vix_spot()
    d["vxf_price"], d["vxf_is_estimated"] = fetch_vix_futures(d["vix_price"])
    try:
        f_res = requests.get("https://production.dataviz.cnn.io/index/feargreed/static/feargreed", headers={"User-Agent":"Mozilla/5.0"}, timeout=10).json()
        d["fgi_score"] = int(f_res['fgi']['now']['value'])
    except: d["fgi_score"] = 0
    
    targets = {"gold": "GC=F", "wti": "CL=F", "nq": "NQ=F", "nk": "NK=F", "es": "ES=F", "us10y": "%5ETNX", "us2y": "%5EIRX", "btc": "BTC-USD"}
    for k, s in targets.items():
        try:
            r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{s}", headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
            m = r["chart"]["result"][0]["meta"]
            d[f"{k}_price"], d[f"{k}_change"] = m["regularMarketPrice"], (m["regularMarketPrice"] - m["chartPreviousClose"]) / m["chartPreviousClose"] * 100
        except: d[f"{k}_price"], d[f"{k}_change"] = 0.0, 0.0
    
    d["yield_spread"] = d["us10y_price"] - d["us2y_price"]
    d["yield_text"] = get_yield_comment(d["yield_spread"], d["us10y_change"])
    return d

# ============================
# メッセージ構築
# ============================
def build_message(d):
    vix_p = d["vix_price"]
    mode, max_s = ("戦時モード：総合反転スコア", 155) if vix_p >= 20 else ("平時モード：トレンドスコア", 135)
    
    score = 0
    if vix_p >= 20:
        if not d["vxf_is_estimated"] and (d["vix_price"] > d["vxf_price"]): score += 30
        if d["vix_change"] <= -5: score += 25
        if d["us2y_change"] < 0: score += 20
        if d["yield_spread"] < 0: score += 20
        if d["btc_change"] >= 3: score += 15
        if d["nq_change"] > 0: score += 25
        if d["es_change"] > 0: score += 20

    scaled = min(max(int(score / max_s * 100), 0), 100)
    
    # --- 修正ポイント ---
    vix_fut_display = "(取得失敗・現物代用)" if d["vxf_is_estimated"] else f"{d['vxf_price']:.2f}"
    
    msg = [
        f"【{datetime.now().strftime('%Y.%m.%d')} {mode}】",
        f"📅 データ日：{d['data_date']}\n",
        f"▼ 投資家心理 (Fear & Greed Index)",
        f"{get_fgi_detail(d['fgi_score'])}\n",
        f"▼ 主要リスク指標",
        f"VIX現物: {d['vix_price']:.2f}（{d['vix_change']:.2f}%）",
        f"VIX先物: {vix_fut_display}",
        f" 💡 {get_vix_analysis(d['vix_price'], d['vxf_price'], d['vxf_is_estimated'])}\n",
        "▼ 金利・イールドカーブ",
        f"・米2年金利 : {d['us2y_price']:.2f}（{d['us2y_change']:.2f}%）",
        f"・米10年金利: {d['us10y_price']:.2f}（{d['us10y_change']:.2f}%）",
        f"・金利差(10Y-2Y): {d['yield_spread']:.3f}",
        f"   💡 {d['yield_text']}\n",
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
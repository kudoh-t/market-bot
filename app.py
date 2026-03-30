import requests
import json
import os
import pickle
import time
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup
import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# ============================
# 設定：環境変数
# ============================
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CACHE_FILE = "market_cache.pkl"

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    ai_model = genai.GenerativeModel('gemini-2.0-flash')

# ============================
# ユーティリティ・送信
# ============================
def send_line(text: str):
    if not LINE_ACCESS_TOKEN or not LINE_USER_ID:
        print("LINE設定がありません。標準出力します:\n", text)
        return
    url = "https://api.line.me/v2/bot/message/push"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {LINE_ACCESS_TOKEN}"}
    body = {"to": LINE_USER_ID, "messages": [{"type": "text", "text": text}]}
    try:
        res = requests.post(url, headers=headers, data=json.dumps(body), timeout=10)
        res.raise_for_status()
    except Exception as e:
        print(f"LINE送信エラー: {e}")

# ============================
# 詳細判定ロジック
# ============================
def get_fgi_detail(now_val, prev_val):
    if now_val is None: return "⚠️Fear & Greed Index：データ取得失敗"
    status = "極度の恐怖" if now_val <= 25 else "恐怖" if now_val <= 45 else "中立" if now_val <= 55 else "強欲" if now_val <= 75 else "極度の強欲"
    change = f"（前日比：{now_val - prev_val:+.0f}pt）" if prev_val is not None else ""
    return f"【{status}】 指数: {now_val} {change}"

def get_vix_analysis(v_spot, v_fut, is_estimated):
    if v_spot is None: return "⚠️VIXデータ欠損"
    diff = v_spot - (v_fut or 0)
    if diff > 0.5: return f"🚨異常(逆転)：現物が先物を{diff:.2f}上回るパニック。反転間近。"
    return "✅正常：市場は落ち着いています。"

def get_yield_detail(spread, us10y_c):
    if spread is None: return "⚠️データ不足。"
    if spread < 0: return "🚨逆イールド：景気後退の強い予兆。"
    if spread > 0.7: return "🔥急拡大：金利暴走による価格調整に注意。"
    return "✅順イールド：金利体系は安定。"

def get_commodities_analysis(gold_c, wti_c, cop_c):
    if any(v is None for v in [gold_c, wti_c, cop_c]): return "⚠️商品データ不足。"
    if (gold_c or 0) > 0.5 and (wti_c or 0) > 1.0: return "🚨【有事・インフレ】金と原油が同時高。株に重石。"
    if (gold_c or 0) > 0.5 and (cop_c or 0) < -1.0: return "📉【景気後退懸念】銅安・金高。安全資産へ逃避。"
    if (cop_c or 0) > 1.0 and (wti_c or 0) > 1.0: return "🏗️【需要増】景気敏感資源が堅調。株に追い風。"
    return "⚖️【中立】明確なコモディティシグナルなし。"

def get_btc_comment(btc_change):
    if btc_change is None: return "⚠️BTC取得失敗。"
    if btc_change > 3.0: return "🚀【リスクオン】投機資金が旺盛。強気。"
    if btc_change < -3.0: return "💀【パニック】資金流出。株への波及警戒。"
    return "⚖️【安定】リスク許容度は維持。"

def get_equity_relative_comment(nk_c, nq_c, es_c):
    valid_us = [c for c in [nq_c, es_c] if c is not None]
    if nk_c is None or not valid_us: return "⚠️相対強弱：データ不足。"
    us_avg = sum(valid_us) / len(valid_us)
    diff = nk_c - us_avg
    if diff >= 0.5: return f"🇯🇵日本優位（乖離:{diff:+.2f}%）"
    if diff <= -0.5: return f"🇺🇸米国優位（乖離:{diff:+.2f}%）"
    return "⚖️日米拮抗"

# ============================
# データ取得
# ============================
def fetch_yahoo_price(symbol):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
        m = res["chart"]["result"][0]["meta"]
        price = m["regularMarketPrice"]
        change = (price - m["chartPreviousClose"]) / m["chartPreviousClose"] * 100
        return price, change
    except: return None, None

def fetch_vix_spot_with_date():
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX"
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
        r = res["chart"]["result"][0]["meta"]
        dt = (datetime.fromtimestamp(r["regularMarketTime"], timezone.utc) + timedelta(hours=9)).strftime("%Y.%m.%d")
        p = r["regularMarketPrice"]
        c = (p - r["chartPreviousClose"]) / r["chartPreviousClose"] * 100
        return p, c, dt
    except: return None, None, "不明"

def get_market_data():
    d = {}
    try:
        f_res = requests.get("https://production.dataviz.cnn.io/index/feargreed/static/feargreed", headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
        d["fgi_score"], d["fgi_prev"] = int(f_res["fgi"]["now"]["value"]), int(f_res["fgi"]["previous"]["value"])
    except: d["fgi_score"], d["fgi_prev"] = None, None
    
    d["vix_p"], d["vix_c"], d["date"] = fetch_vix_spot_with_date()
    # VIX先物の代用としてVXV(3ヶ月VIX)を使用
    p_vxv, _ = fetch_yahoo_price("%5EVXV")
    d["vxf_p"], d["vxf_est"] = p_vxv, True
    
    targets = {"nq":"NQ=F", "es":"ES=F", "nk":"NK=F", "gold":"GC=F", "wti":"CL=F", "cop":"HG=F", "u10":"%5ETNX", "btc":"BTC-USD"}
    for k, s in targets.items(): d[f"{k}_p"], d[f"{k}_c"] = fetch_yahoo_price(s)
    
    for s in ["2Y=F", "^IRX", "^ZYY"]:
        p, c = fetch_yahoo_price(s)
        if p: d["u2_p"], d["u2_c"] = p, c; break
    else: d["u2_p"], d["u2_c"] = None, None

    d["spread"] = (d["u10_p"] - d["u2_p"]) if d.get("u10_p") and d.get("u2_p") else None
    return d

# ============================
# メッセージ構築
# ============================
def build_message(d):
    vix_p = d.get("vix_p") or 0
    score = 0
    if (d.get("nq_c") or 0) > 0: score += 25
    if (d.get("es_c") or 0) > 0: score += 20
    if (d.get("nk_c") or 0) > 0: score += 20
    if vix_p >= 20:
        if (d.get("vix_p") or 0) > (d.get("vxf_p") or 0): score += 30
        if (d.get("spread") or 0) < 0: score += 20
    
    scaled = min(max(int(score / 155 * 100), 0), 100)
    def fmt(p, c, dec=2): return f"{p:.{dec}f}（{c:+.2f}%）" if p is not None else "取得失敗"

    msg = [
        f"【{datetime.now().strftime('%Y.%m.%d')} 市場診断】",
        f"📅 更新：{d.get('date')}\n",
        "▼ 1. 投資家心理 (FGI)", f" {get_fgi_detail(d.get('fgi_score'), d.get('fgi_prev'))}\n",
        "▼ 2. 主要指数先物 & 相対強弱",
        f" ・米 NQ100 : {fmt(d.get('nq_p'), d.get('nq_c'))}",
        f" ・米 S&P500: {fmt(d.get('es_p'), d.get('es_c'))}",
        f" ・日経平均 : {fmt(d.get('nk_p'), d.get('nk_c'))}",
        f" 💡 {get_equity_relative_comment(d.get('nk_c'), d.get('nq_c'), d.get('es_c'))}\n",
        "▼ 3. リスク指標 (VIX)",
        f" ・VIX現物: {fmt(d.get('vix_p'), d.get('vix_c'))}",
        f" 💡 {get_vix_analysis(d.get('vix_p'), d.get('vxf_p'), d.get('vxf_est'))}\n",
        "▼ 4. 金利・イールド",
        f" ・米10年債: {fmt(d.get('u10_p'), d.get('u10_c'))}",
        f" ・米 2年債: {fmt(d.get('u2_p'), d.get('u2_c'))}",
        f" ・利回り差: {d.get('spread'):.3f}" if d.get('spread') is not None else " ・利回り差: 失敗",
        f" 💡 {get_yield_detail(d.get('spread'), d.get('u10_c'))}\n",
        "▼ 5. 商品 (Commodities)",
        f" ・金 (Gold): {fmt(d.get('gold_p'), d.get('gold_c'), 1)}",
        f" ・原油(WTI): {fmt(d.get('wti_p'), d.get('wti_c'))}",
        f" ・銅 (Cop) : {fmt(d.get('cop_p'), d.get('cop_c'), 3)}",
        f" 💡 {get_commodities_analysis(d.get('gold_c'), d.get('wti_c'), d.get('cop_c'))}\n",
        "▼ 6. 仮想通貨 (Crypto)",
        f" ・BTC: ${fmt(d.get('btc_p'), d.get('btc_c'), 0)}",
        f" 💡 {get_btc_comment(d.get('btc_c'))}\n",
        f"⚖️ 総合スコア：{scaled}点 / 100",
        f" {'📈 反転の兆し：打診買い検討' if scaled >= 50 else '🌑 有事継続：キャッシュ保護優先'}\n",
        "--------------------------"
    ]
    return "\n".join(msg)

# ============================
# Gemini連携
# ============================
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=10, min=10, max=60), retry=retry_if_exception_type(Exception))
def fetch_gemini_content(prompt):
    if not GEMINI_API_KEY: return "（AI評価未設定）"
    return ai_model.generate_content(prompt).text.strip()

# ============================
# メイン
# ============================
def main():
    data = get_market_data()
    report = build_message(data)
    
    print("Gemini解析中...")
    try:
        feedback = fetch_gemini_content(f"プロのストラテジストとして短評をください：\n{report}")
    except:
        feedback = "⚠️Gemini API制限により取得失敗。"
        
    final_msg = f"{report}\n\n--- 🤖 Gemini's View ---\n{feedback}"
    send_line(final_msg)

if __name__ == "__main__":
    main()
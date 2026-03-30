import requests
import json
import os
import pickle
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

# ============================
# 設定：環境変数
# ============================
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")
CACHE_FILE = "market_cache.pkl"

def send_line(text: str):
    if not LINE_ACCESS_TOKEN or not LINE_USER_ID:
        print("LINE設定がありません。標準出力します:\n", text)
        return
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_ACCESS_TOKEN}"
    }
    body = {
        "to": LINE_USER_ID,
        "messages": [{"type": "text", "text": text}]
    }
    try:
        requests.post(url, headers=headers, data=json.dumps(body), timeout=10)
    except Exception:
        pass

# ============================
# 判定・解説ロジック
# ============================
def get_vix_analysis(v_spot, v_fut, is_estimated):
    if v_spot is None:
        return "⚠️VIX現物データ取得失敗：リスク指標の精度低下に注意。"
    est_msg = "（※先物代用値で診断中）" if is_estimated else ""
    if v_fut is None:
        return f"⚠️VIX先物データ取得失敗：現物のみで判定。{est_msg}"
    diff = v_spot - v_fut
    if diff > 0.5:
        return f"🚨異常乖離(逆転)：現物が先物を{diff:.2f}上回るパニック状態。底打ちが近いサイン。{est_msg}"
    elif diff < -1.0:
        return f"✅正常乖離(順鞘)：市場は落ち着いています。{est_msg}"
    else:
        return f"😐均衡状態：方向感を模索中です。{est_msg}"

def get_fgi_detail(now_val, prev_val):
    if now_val is None: return "⚠️Fear & Greed Index：データ取得失敗"
    change_str = f"前日比：{now_val - prev_val:+.0f}pt" if prev_val is not None else ""
    if now_val <= 25: base = f"🧊指数({now_val}): 極度の恐怖。歴史的には仕込み場。"
    elif now_val <= 45: base = f"😨指数({now_val}): 恐怖。警戒が強い状態。"
    elif now_val <= 55: base = f"😐指数({now_val}): 中立。強弱感が拮抗。"
    elif now_val <= 75: base = f"🚀指数({now_val}): 強欲。利確優先。"
    else: base = f"🚨指数({now_val}): 極度の強欲。急落警戒。"
    return f"{base}（{change_str}）"

def get_yield_comment(spread, us10y_change):
    if spread is None: return "⚠️金利データ取得失敗。"
    if spread < 0: return "⚠️逆イールド：景気後退の強い予兆。"
    elif spread >= 0.5 and (us10y_change or 0) > 0: return "⚡急激なスティープニング：長期金利急騰注意。"
    elif 0 <= spread < 0.2: return "🔄フラット化：反転の兆し。金利上昇なら株に逆風。"
    else: return "✅順イールド：金利体系は正常。"

def get_commodities_combined_analysis(gold_c, wti_c, cop_c):
    """金・原油・銅の3要素を統合分析"""
    if any(v is None for v in [gold_c, wti_c, cop_c]):
        return "⚠️商品データ不足：複合分析不可。"
    
    # パターン判定
    if gold_c > 1.0 and wti_c > 1.5:
        return "🚨【地政学・インフレ警戒】金と原油が同時急騰。コストプッシュ・インフレが株価の重石に。"
    elif gold_c > 0.5 and wti_c < -1.0 and cop_c < -1.0:
        return "📉【景気後退懸念】銅と原油が売られ金に逃避。実需冷え込みを示唆する強いリスクオフ。"
    elif gold_c < -0.5 and (wti_c > 1.0 or cop_c > 1.0):
        return "🏗️【景気拡大・需要増】銅や原油に買い。実需を伴う経済活動の活性化。株には追い風。"
    elif gold_c > 0.5 and cop_c < -1.0 and wti_c > 0.5:
        return "⚠️【不吉な兆候】景気指標(銅)は弱いが燃料(原油)は高い。スタグフレーションに注意。"
    elif gold_c < 0 and wti_c < 0 and cop_c < 0:
        return "✅【リスク安定】商品から資金が抜け、株式等のリスク資産へ回る好循環。"
    return "⚖️【均衡状態】各商品の動きがまちまちで、明確なマクロシグナルなし。"

def get_btc_comment(btc_change):
    if btc_change is None: return "⚠️BTCデータ取得失敗。"
    if btc_change > 3.0: return "🚀【リスクオン爆発】投機資金が猛烈流入。地合いは極めて強気。"
    elif btc_change > 0.5: return "₿【堅調】リスク許容度が維持されています。株価の下支え要因。"
    elif btc_change < -3.0: return "💀【リスクオフ波及】仮想通貨から資金流出。投げ売りへの連鎖に警戒。"
    elif btc_change < -0.5: return "📉【弱含み】投資家が慎重姿勢。リスク回避の動き。"
    return "⚖️【横ばい】仮想通貨市場は安定。波及効果は限定的。"

def get_equity_relative_comment(nk_change, nq_change, es_change):
    if nk_change is None or (nq_change is None and es_change is None): return "⚠️日米相対強弱：データ不足。"
    us_avg = sum([c for c in [nq_change, es_change] if c is not None]) / 2
    diff = nk_change - us_avg
    if diff >= 0.5: return f"🇯🇵日本優位：日経先物が米株を約{diff:.2f}%上回る相対的な強さ。"
    elif diff <= -0.5: return f"🇺🇸米国優位：日経先物が約{abs(diff):.2f}%下回る出遅れ状態。"
    return "⚖️日米拮抗：明確な優劣なし。"

def get_score_comment(scaled):
    if scaled >= 80: return "💎【反転確定ゾーン】複数の反転シグナル点灯。攻めに転じる好機。"
    if scaled >= 50: return "📈【反転の兆し】買い戻しの動き。打診買い検討圏内。"
    if scaled >= 30: return "⚠️【初期兆候】下げ止まりの兆しはあるが慎重に。"
    return "🌑【有事継続】キャッシュ保護を優先。"

def analyze_market_action(d):
    actions = []
    if (d.get("vix_price") or 0) > (d.get("vxf_price") or 0) + 0.5:
        actions.append("⚠️【VIX逆転】異常事態。パニック売りに乗らず反転待ち。")
    if (d.get("us10y_change") or 0) > 1.2 and (d.get("nq_change") or 0) < -0.8:
        actions.append("📉【金利の重力】長期金利急騰で株価に強い逆風。買い増し危険。")
    return "\n\n".join(actions[:2]) if actions else "🧐【特筆事項なし】トレンド待ち。"

# ============================
# データ取得
# ============================
def fetch_yahoo_price(symbol):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
        m = res["chart"]["result"][0]["meta"]
        price, prev = m["regularMarketPrice"], m["chartPreviousClose"]
        return price, (price - prev) / prev * 100
    except Exception: return None, None

def fetch_vix_spot():
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX"
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
        r = res["chart"]["result"][0]["meta"]
        p, pr = r["regularMarketPrice"], r["chartPreviousClose"]
        dt = (datetime.fromtimestamp(r["regularMarketTime"], timezone.utc) + timedelta(hours=9)).strftime("%Y.%m.%d")
        return p, (p - pr) / pr * 100, dt
    except Exception: return None, None, "取得失敗"

def fetch_vix_futures_multi():
    try:
        url = "https://www.investing.com/indices/us-spx-vix-futures"
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        p_el = soup.select_one('[data-test="instrument-price-last"]')
        c_el = soup.select_one('[data-test="instrument-price-change-percent"]')
        if p_el and c_el:
            p = float(p_el.text.replace(",", "").strip())
            c = float(c_el.text.replace("%", "").replace("+", "").strip())
            return p, c, False
    except Exception: pass
    p_vxv, c_vxv = fetch_yahoo_price("%5EVXV")
    return (p_vxv, c_vxv, True) if p_vxv else (None, None, True)

def fetch_fgi_multi():
    try:
        res = requests.get("https://production.dataviz.cnn.io/index/feargreed/static/feargreed", 
                           headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
        return int(res["fgi"]["now"]["value"]), int(res["fgi"]["previous"]["value"])
    except Exception: pass
    return None, None

def get_market_data():
    d = {}
    d["vix_price"], d["vix_change"], d["data_date"] = fetch_vix_spot()
    d["vxf_price"], d["vxf_change"], d["vxf_is_estimated"] = fetch_vix_futures_multi()
    d["fgi_score"], d["fgi_prev"] = fetch_fgi_multi()

    targets = {"gold":"GC=F", "wti":"CL=F", "copper":"HG=F", "nq":"NQ=F", "nk":"NK=F", "es":"ES=F", "us10y":"%5ETNX", "us2y":"%5EIRX", "btc":"BTC-USD"}
    for k, s in targets.items():
        d[f"{k}_price"], d[f"{k}_change"] = fetch_yahoo_price(s)

    if d["us10y_price"] is not None and d["us2y_price"] is not None:
        d["yield_spread"] = d["us10y_price"] - d["us2y_price"]
    else: d["yield_spread"] = None

    d["yield_text"] = get_yield_comment(d["yield_spread"], d["us10y_change"])
    if d["vix_price"] is not None:
        with open(CACHE_FILE, "wb") as f: pickle.dump(d, f)
    elif os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "rb") as f: d = pickle.load(f)
        d["data_date"] += " (Cache)"
    return d

# ============================
# メッセージ構築
# ============================
def fmt_p(p, c, dec=2):
    if p is None: return "取得失敗"
    return f"{p:.{dec}f}（{c:+.2f}%）" if c is not None else f"{p:.{dec}f}"

def build_message(d):
    vix_p = d.get("vix_price") or 0
    mode, max_s = ("戦時モード：総合反転スコア", 155) if vix_p >= 20 else ("平時モード：トレンドスコア", 135)
    
    score = 0
    if vix_p >= 20:
        if (d.get("vix_price") or 0) > (d.get("vxf_price") or 0): score += 30
        if (d.get("vix_change") or 0) <= -5: score += 25
        if (d.get("us2y_change") or 0) < 0: score += 20
        if (d.get("yield_spread") or 0) < 0: score += 20
        if (d.get("btc_change") or 0) >= 3: score += 15
        if (d.get("nq_change") or 0) > 0: score += 25
        if (d.get("es_change") or 0) > 0: score += 20
    scaled = min(max(int(score / max_s * 100), 0), 100)
    
    msg = [
        f"【{datetime.now().strftime('%Y.%m.%d')} {mode}】",
        f"📅 データ日：{d.get('data_date')}\n",
        "▼ 投資家心理 (FGI)",
        f"{get_fgi_detail(d.get('fgi_score'), d.get('fgi_prev'))}\n",
        "▼ リスク指標",
        f"VIX現物: {fmt_p(d.get('vix_price'), d.get('vix_change'))}",
        f"VIX先物: {fmt_p(d.get('vxf_price'), d.get('vxf_change'))}",
        f" 💡 {get_vix_analysis(d.get('vix_price'), d.get('vxf_price'), d.get('vxf_is_estimated'))}\n",
        "▼ 金利/イールド",
        f"・米10Y : {fmt_p(d.get('us10y_price'), d.get('us10y_change'))}",
        f"・10Y-2Y: {d.get('yield_spread'):.3f}" if d.get('yield_spread') else "・金利差: 失敗",
        f" 💡 {d.get('yield_text')}\n",
        "▼ 商品 (Commodities)",
        f"・金 : {fmt_p(d.get('gold_price'), d.get('gold_change'), 1)}",
        f"・原油: {fmt_p(d.get('wti_price'), d.get('wti_change'), 2)}",
        f"・銅 : {fmt_p(d.get('copper_price'), d.get('copper_change'), 3)}",
        f" 💡 {get_commodities_combined_analysis(d.get('gold_change'), d.get('wti_change'), d.get('copper_change'))}\n",
        "▼ 暗号資産 (Crypto)",
        f"・BTC : ${fmt_p(d.get('btc_price'), d.get('btc_change'), 0)}",
        f" 💡 {get_btc_comment(d.get('btc_change'))}\n",
        "▼ 日米相対強弱",
        get_equity_relative_comment(d.get("nk_change"), d.get("nq_change"), d.get("es_change")) + "\n",
        f"⚖️ スコア評価：{scaled}点 / 100",
        f"{get_score_comment(scaled)}\n",
        "--------------------------",
        "💡 【行動指針】",
        analyze_market_action(d)
    ]
    return "\n".join(msg)

# ============================
# 追加設定：Gemini API
# ============================
# Google AI Studio (https://aistudio.google.com/) で取得したキーを設定
import os
import google.generativeai as genai

# GitHubの環境変数からキーを取得（.envファイルがなくてもActions上では動きます）
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    ai_model = genai.GenerativeModel('gemini-2.0-flash')
def get_gemini_opinion(market_text: str):
    """
    作成した分析レポートをGeminiに送り、ざっくりとした感想をもらう
    """
    if not GEMINI_API_KEY:
        return "（Gemini APIキーが設定されていないため、AI評価はスキップされました）"

    # あえて「ざっくり」としたプロンプトに設定
    prompt = f"""
    以下の市場分析レポートを読んで、プロのストラテジストとして「どう思いますか？」
    率直な感想や、このロジックでカバーできていない懸念点、あるいは注目すべきポジティブな兆候など、
    あなたの視点で自由にコメントしてください。

    【分析レポート】
    {market_text}
    """

    try:
        response = ai_model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"⚠️Gemini評価取得中にエラーが発生しました: {e}"

# ============================
# メイン処理（ここを差し替え）
# ============================
def main():
    # 1. 既存のロジックでデータを取得
    data = get_market_data()
    
    # 2. 自分で作った分析メッセージを構築
    my_report = build_message(data)
    
    # 3. Geminiに「どう思う？」と聞く
    print("Geminiに意見を求めています...")
    ai_feedback = get_gemini_opinion(my_report)
    
    # 4. 自分のレポートとGeminiの意見を合体させる
    final_message = (
        f"{my_report}\n\n"
        "--- 🤖 Gemini's View ---\n"
        f"{ai_feedback}"
    )
    
    # 5. LINEに送信
    send_line(final_message)

if __name__ == "__main__":
    main()
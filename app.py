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
CACHE_FILE = "market_cache.pkl"  # 最終正常データの保存用

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
    
    # 推定値（VXV等）を使用している場合の注釈
    est_msg = "（※先物代用値で診断中）" if is_estimated else ""

    if v_fut is None:
        return f"⚠️VIX先物データ取得失敗：現物のみで診断中。{est_msg}"

    diff = v_spot - v_fut
    if diff > 0.5:
        return f"🚨異常乖離(逆転)：現物が先物を{diff:.2f}上回るパニック状態。底打ちが近いサインです。{est_msg}"
    elif diff < -1.0:
        return f"✅正常乖離(順鞘)：先物の方が高い正常な状態。市場は落ち着いています。{est_msg}"
    else:
        return f"😐均衡状態：方向感を模索中です。{est_msg}"

def get_fgi_detail(now_val, prev_val):
    if now_val is None:
        return "⚠️Fear & Greed Index：データ取得失敗（全ソースエラー）"

    change_str = "前日比：取得失敗"
    if prev_val is not None:
        change = now_val - prev_val
        sign = "+" if change > 0 else ""
        change_str = f"前日比：{sign}{change:.0f}pt"

    if now_val <= 25:
        base = f"🧊指数({now_val}): 極度の恐怖。歴史的には仕込み場。"
    elif now_val <= 45:
        base = f"😨指数({now_val}): 恐怖。下落への警戒が強い状態。"
    elif now_val <= 55:
        base = f"😐指数({now_val}): 中立。強弱感が拮抗。"
    elif now_val <= 75:
        base = f"🚀指数({now_val}): 強欲。利益確定を優先。"
    else:
        base = f"🚨指数({now_val}): 極度の強欲。急落警戒。"

    return f"{base}（{change_str}）"

def get_yield_comment(spread, us10y_change):
    if spread is None:
        return "⚠️金利データ取得失敗：イールドカーブ判定不可。"
    if spread < 0:
        return "⚠️逆イールド：景気後退の強い予兆。"
    elif spread >= 0.5 and (us10y_change is not None and us10y_change > 0):
        return "⚡急激なスティープニング：長期金利急騰。債券売りに注意。"
    elif 0 <= spread < 0.2:
        return "🔄フラット化：反転の兆し。ただし金利上昇なら株には逆風。"
    else:
        return "✅順イールド：金利体系は正常。上昇速度に注意。"

def get_score_comment(scaled):
    if scaled >= 80:
        return "💎【反転確定ゾーン】複数の反転シグナル点灯。攻めに転じる好機。"
    if scaled >= 50:
        return "📈【反転の兆し】買い戻しの動き。打診買い検討圏内。"
    if scaled >= 30:
        return "⚠️【初期兆候】下げ止まりの兆しはあるが、まだ不安定。慎重に。"
    return "🌑【有事継続】無理な逆張りは避け、キャッシュ保護を優先。"

def analyze_market_action(d):
    actions = []
    if d["vix_price"] is not None and d["vxf_price"] is not None and d["vix_price"] > d["vxf_price"] + 0.5:
        actions.append("⚠️【VIX逆転】現物が先物を上回る異常事態。パニック売りに乗らず反転待ち。")
    if (d["us10y_change"] is not None and d["us10y_change"] > 1.2 and d["nq_change"] is not None and d["nq_change"] < -0.8):
        actions.append("📉【金利の重力】長期金利急騰で株価に強い逆風。買い増しは危険。")
    if (d["gold_change"] is not None and d["gold_change"] > 2.0 and d["wti_change"] is not None and d["wti_change"] > 3.0):
        actions.append("🛢️【有事の動き】金と原油の同時急騰は地政学リスク。株には逆風。")
    return "\n\n".join(actions[:2]) if actions else "🧐【特筆事項なし】目立った歪みなし。トレンド待ち。"

def get_btc_comment(btc_change):
    if btc_change is None: return "⚠️BTCデータ取得失敗。"
    if btc_change > 1.5: return "₿リスクオン気味：投資家のリスク許容度が回復。"
    elif btc_change >= 0: return "₿小幅上昇：リスクオフ局面でも底堅い動き。"
    else: return "₿リスクオフ：全体的にリスク回避姿勢が強い。"

def get_equity_relative_comment(nk_change, nq_change, es_change):
    if nk_change is None or (nq_change is None and es_change is None):
        return "⚠️日米相対強弱：データ不足。"
    us_changes = [c for c in [nq_change, es_change] if c is not None]
    if not us_changes: return "⚠️日米相対強弱：米株データ不足。"
    us_avg = sum(us_changes) / len(us_changes)
    diff = nk_change - us_avg
    if diff >= 1.0: return f"🇯🇵日本優位：日経先物が米株を約{diff:.2f}%上回る。米株の下げが主因か。"
    elif diff >= 0.3: return f"🇯🇵やや日本優位：日経先物が約{diff:.2f}%上回る。相対的に底堅い。"
    elif diff <= -1.0: return f"🇺🇸米国優位：日経先物が約{abs(diff):.2f}%下回る。日本株は出遅れ。"
    elif diff <= -0.3: return f"🇺🇸やや米国優位：日経先物が約{abs(diff):.2f}%下回る。日本株は相対的に弱い。"
    return "⚖️日米拮抗：騰落率差は小さく、明確な優劣なし。"

# ============================
# データ取得（多重化スキーム）
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
    except Exception: return None, None, "データ取得失敗"

def fetch_vix_futures_multi():
    """VIX先物の多重化：Investing.com -> Yahoo(^VXV)"""
    # 1. Investing.com (本命)
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

    # 2. Yahoo Finance ^VXV (3ヶ月VIX指数) で代用
    p_vxv, c_vxv = fetch_yahoo_price("%5EVXV")
    if p_vxv: return p_vxv, c_vxv, True # 推定フラグTrue

    return None, None, True

def fetch_fgi_multi():
    """FGIの多重化：CNN -> Alternative.me"""
    # 1. CNN API
    try:
        res = requests.get("https://production.dataviz.cnn.io/index/feargreed/static/feargreed", 
                           headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
        return int(res["fgi"]["now"]["value"]), int(res["fgi"]["previous"]["value"])
    except Exception: pass

    # 2. Alternative.me (Crypto F&Gだが代替として利用)
    try:
        res = requests.get("https://api.alternative.me/fng/", timeout=10).json()
        return int(res['data'][0]['value']), None
    except Exception: pass

    return None, None

def get_market_data():
    d = {}
    d["vix_price"], d["vix_change"], d["data_date"] = fetch_vix_spot()
    d["vxf_price"], d["vxf_change"], d["vxf_is_estimated"] = fetch_vix_futures_multi()
    d["fgi_score"], d["fgi_prev"] = fetch_fgi_multi()

    targets = {"gold":"GC=F", "wti":"CL=F", "nq":"NQ=F", "nk":"NK=F", "es":"ES=F", "us10y":"%5ETNX", "us2y":"%5EIRX", "btc":"BTC-USD"}
    for k, s in targets.items():
        d[f"{k}_price"], d[f"{k}_change"] = fetch_yahoo_price(s)

    if d["us10y_price"] is not None and d["us2y_price"] is not None:
        d["yield_spread"] = d["us10y_price"] - d["us2y_price"]
    else: d["yield_spread"] = None

    d["yield_text"] = get_yield_comment(d["yield_spread"], d["us10y_change"])
    
    # --- キャッシュ処理 ---
    if d["vix_price"] is not None:
        with open(CACHE_FILE, "wb") as f: pickle.dump(d, f)
    elif os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "rb") as f: d = pickle.load(f)
        d["data_date"] += " (Cache)"
    
    return d

# ============================
# メッセージ構築・表示用
# ============================
def fmt_p(p, c, dec=2):
    if p is None: return "取得失敗"
    sign = "+" if (c or 0) > 0 else ""
    return f"{p:.{dec}f}（前日比：{sign}{c if c is not None else 0:.2f}%）"

def build_message(d):
    vix_p = d.get("vix_price") or 0
    mode, max_s = ("戦時モード：総合反転スコア", 155) if vix_p >= 20 else ("平時モード：トレンドスコア", 135)

    score = 0
    if vix_p >= 20:
        if d.get("vix_price") and d.get("vxf_price") and d["vix_price"] > d["vxf_price"]: score += 30
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
        "▼ 投資家心理 (Fear & Greed Index)",
        f"{get_fgi_detail(d.get('fgi_score'), d.get('fgi_prev'))}\n",
        "▼ 主要リスク指標",
        f"VIX現物: {fmt_p(d.get('vix_price'), d.get('vix_change'))}",
        f"VIX先物: {fmt_p(d.get('vxf_price'), d.get('vxf_change'))}",
        f" 💡 {get_vix_analysis(d.get('vix_price'), d.get('vxf_price'), d.get('vxf_is_estimated'))}\n",
        "▼ 金利・イールドカーブ",
        f"・米2年金利 : {fmt_p(d.get('us2y_price'), d.get('us2y_change'))}",
        f"・米10年金利: {fmt_p(d.get('us10y_price'), d.get('us10y_change'))}",
        f"・金利差(10Y-2Y): {d.get('yield_spread'):.3f}" if d.get('yield_spread') else "・金利差: 取得失敗",
        f"   💡 {d.get('yield_text')}\n",
        "▼ 商品 / 暗号資産",
        f"・ゴールド : {fmt_p(d.get('gold_price'), d.get('gold_change'), 1)}",
        f"・BTC : ${fmt_p(d.get('btc_price'), d.get('btc_change'), 0)}\n",
        "▼ 日米相対強弱",
        get_equity_relative_comment(d.get("nk_change"), d.get("nq_change"), d.get("es_change")) + "\n",
        f"⚖️ スコア評価：{scaled}点 / 100",
        f"（生スコア: {score} / {max_s}）",
        f"{get_score_comment(scaled)}\n",
        "--------------------------",
        "💡 【行動指針】",
        analyze_market_action(d)
    ]
    return "\n".join(msg)

def main():
    data = get_market_data()
    send_line(build_message(data))

if __name__ == "__main__":
    main()
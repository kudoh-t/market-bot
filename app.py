import requests
import json
import os
import pickle
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup
import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential

# ============================
# 設定：環境変数
# ============================
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CACHE_FILE = "market_cache.pkl"
GEMINI_CACHE_FILE = "gemini_cache.pkl"

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    ai_model = genai.GenerativeModel("gemini-2.0-flash")

# ============================
# キャッシュ関連
# ============================
def load_prev_data():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "rb") as f:
                return pickle.load(f)
        except Exception:
            return {}
    return {}

def save_data_cache(d):
    try:
        with open(CACHE_FILE, "wb") as f:
            pickle.dump(d, f)
    except Exception as e:
        print(f"キャッシュ保存エラー: {e}")

def load_prev_gemini():
    if os.path.exists(GEMINI_CACHE_FILE):
        try:
            with open(GEMINI_CACHE_FILE, "rb") as f:
                return pickle.load(f)
        except Exception:
            return "前回のAI評価取得失敗"
    return "前回のAI評価なし"

def save_gemini_cache(text: str):
    try:
        with open(GEMINI_CACHE_FILE, "wb") as f:
            pickle.dump(text, f)
    except Exception as e:
        print(f"Geminiキャッシュ保存エラー: {e}")

# ============================
# ユーティリティ・送信
# ============================
def send_line(text: str):
    if not LINE_ACCESS_TOKEN or not LINE_USER_ID:
        print("LINE設定がありません。標準出力します:\n", text)
        return
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_ACCESS_TOKEN}",
    }
    body = {"to": LINE_USER_ID, "messages": [{"type": "text", "text": text}]}
    try:
        res = requests.post(url, headers=headers, data=json.dumps(body), timeout=10)
        res.raise_for_status()
    except Exception as e:
        print(f"LINE送信エラー: {e}")

# ============================
# 判定ロジック
# ============================
def get_fgi_detail(now_val, prev_val):
    if now_val is None:
        return "⚠️FGI取得失敗"
    status = (
        "極度の恐怖"
        if now_val <= 25
        else "恐怖"
        if now_val <= 45
        else "中立"
        if now_val <= 55
        else "強欲"
        if now_val <= 75
        else "極度の強欲"
    )
    change = (
        f"（前日比：{now_val - prev_val:+.0f}pt）" if prev_val is not None else ""
    )
    return f"【{status}】 指数: {now_val} {change}"

def get_vix_analysis(v_spot, v_fut):
    if v_spot is None:
        return "⚠️VIXデータ欠損"
    if v_fut is None:
        return "⚠️VIX先物データ欠損"
    diff = v_spot - v_fut
    if diff > 0.5:
        return f"🚨異常(逆転)：現物が先物を{diff:.2f}上回るパニック。反転間近。"
    return "✅正常：市場は落ち着いています。"

def get_yield_detail(spread):
    if spread is None:
        return "⚠️データ不足。"
    if spread < 0:
        return "🚨逆イールド：景気後退の強い予兆。"
    if spread > 0.7:
        return "🔥急拡大：金利暴走による価格調整に注意。"
    return "✅順イールド：金利体系は安定。"

def get_commodities_analysis(gold_c, wti_c, cop_c):
    if any(v is None for v in [gold_c, wti_c, cop_c]):
        return "⚠️商品データ不足。"
    if gold_c > 0.5 and wti_c > 1.0:
        return "🚨【有事・インフレ】金と原油が同時高。株に重石。"
    if gold_c > 0.5 and cop_c < -1.0:
        return "📉【景気後退懸念】銅安・金高。安全資産へ逃避。"
    if cop_c > 1.0 and wti_c > 1.0:
        return "🏗️【需要増】景気敏感資源が堅調。株に追い風。"
    return "⚖️【中立】明確なコモディティシグナルなし。"

def get_btc_comment(btc_change):
    if btc_change is None:
        return "⚠️BTC取得失敗。"
    if btc_change > 3.0:
        return "🚀【リスクオン】投機資金が旺盛。強気。"
    if btc_change < -3.0:
        return "💀【パニック】資金流出。株への波及警戒。"
    return "⚖️【安定】リスク許容度は維持。"

def get_equity_relative_comment(nk_c, nq_c, es_c):
    valid_us = [c for c in [nq_c, es_c] if c is not None]
    if nk_c is None or not valid_us:
        return "⚠️相対強弱：データ不足。"
    us_avg = sum(valid_us) / len(valid_us)
    diff = nk_c - us_avg
    if diff >= 0.5:
        return f"🇯🇵日本優位（乖離:{diff:+.2f}%）"
    if diff <= -0.5:
        return f"🇺🇸米国優位（乖離:{diff:+.2f}%）"
    return "⚖️日米拮抗"

# ============================
# データ取得
# ============================
def fetch_yahoo(symbol):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        res = requests.get(
            url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10
        ).json()
        m = res["chart"]["result"][0]["meta"]
        p = m["regularMarketPrice"]
        c = (p - m["chartPreviousClose"]) / m["chartPreviousClose"] * 100
        return p, c
    except Exception:
        return None, None

def fetch_fgi_raw():
    try:
        url = "https://api.alternative.me/fng/?limit=2&format=json"
        res = requests.get(url, timeout=10).json()
        now_val = int(res["data"][0]["value"])
        prev_val = int(res["data"][1]["value"])
        return now_val, prev_val
    except Exception:
        return None, None

def fetch_vix_future_raw():
    try:
        url = "https://www.investing.com/indices/volatility-s-p-500-futures"
        headers = {"User-Agent": "Mozilla/5.0"}
        html = requests.get(url, headers=headers, timeout=1).text
        soup = BeautifulSoup(html, "html.parser")

        price_el = soup.select_one("div[data-test='instrument-price-last']")
        change_el = soup.select_one(
            "span[data-test='instrument-price-change-percent']"
        )
        if not price_el or not change_el:
            return None, None

        price = float(price_el.text.replace(",", ""))
        change_text = (
            change_el.text.replace("%", "").replace("+", "").replace("−", "-")
        )
        change = float(change_text)
        return price, change
    except Exception:
        return None, None

def fill_with_prev(d, prev, key_price, key_change):
    if d.get(key_price) is None and prev.get(key_price) is not None:
        d[key_price] = prev[key_price]
        d[key_change] = 0.0

def get_market_data():
    d = {}
    prev = load_prev_data()

    # FGI（取得失敗時は前回値で補完）
    fgi_now, fgi_prev = fetch_fgi_raw()
    if fgi_now is None:
        fgi_now = prev.get("fgi_score")
        fgi_prev = prev.get("fgi_prev")
    d["fgi_score"], d["fgi_prev"] = fgi_now, fgi_prev

    # VIX現物
    d["vix_p"], d["vix_c"] = fetch_yahoo("%5EVIX")

    # VIX先物（取得失敗時は前回値で補完）
    d["vxf_p"], d["vxf_c"] = fetch_vix_future_raw()

    targets = {
        "nq": "NQ=F",
        "es": "ES=F",
        "nk": "NK=F",
        "gold": "GC=F",
        "wti": "CL=F",
        "cop": "HG=F",
        "u10": "%5ETNX",
        "btc": "BTC-USD",
    }
    for k, s in targets.items():
        d[f"{k}_p"], d[f"{k}_c"] = fetch_yahoo(s)

    # 2年債
    d["u2_p"], d["u2_c"] = None, None
    for s in ["2Y=F", "^IRX", "^ZYY"]:
        p, c = fetch_yahoo(s)
        if p is not None:
            d["u2_p"], d["u2_c"] = p, c
            break

    # 欠損を前回値で補完（VIX先物含む）
    for key in [
        "vix",
        "vxf",
        "nq",
        "es",
        "nk",
        "gold",
        "wti",
        "cop",
        "u10",
        "u2",
        "btc",
    ]:
        fill_with_prev(d, prev, f"{key}_p", f"{key}_c")

    # スプレッド
    d["spread"] = (
        (d.get("u10_p") - d.get("u2_p"))
        if d.get("u10_p") is not None and d.get("u2_p") is not None
        else None
    )

    d["date"] = datetime.now(timezone(timedelta(hours=9))).strftime("%Y.%m.%d")

    save_data_cache(d)
    return d

# ============================
# メッセージ構築
# ============================
def build_message(d):
    prev_data = load_prev_data()
    vix_p = d.get("vix_p") or 0
    prev_vix = prev_data.get("vix_p") or 0

    if vix_p >= 20 and prev_vix < 20:
        mode_title = "⚠️移行モード：警戒開始"
    elif vix_p < 20 and prev_vix >= 20:
        mode_title = "🔄移行モード：沈静化の兆し"
    elif vix_p >= 20:
        mode_title = "🚨戦時モード：総合反転スコア"
    else:
        mode_title = "🍀平時モード：トレンドスコア"

    score = 0
    max_score = 155 if vix_p >= 20 else 135

    if (d.get("nq_c") or 0) > 0:
        score += 25
    if (d.get("es_c") or 0) > 0:
        score += 20
    if (d.get("nk_c") or 0) > 0:
        score += 20

    if vix_p >= 20:
        if d.get("vix_p") is not None and d.get("vxf_p") is not None:
            if d["vix_p"] > d["vxf_p"]:
                score += 30
        if (d.get("spread") or 0) < 0:
            score += 20

    if (d.get("btc_c") or 0) >= 3:
        score += 20

    scaled = min(max(int(score / max_score * 100), 0), 100)

    def fmt(p, c, dec=2):
        return f"{p:.{dec}f}（{c:+.2f}%）" if p is not None else "取得失敗"

    msg = [
        f"【{d.get('date')} {mode_title}】\n",
        "▼ 1. 投資家心理 (FGI)",
        f" {get_fgi_detail(d.get('fgi_score'), d.get('fgi_prev'))}\n",
        "▼ 2. 主要指数先物 & 相対強弱",
        f" ・米 NQ100 : {fmt(d.get('nq_p'), d.get('nq_c'))}",
        f" ・米 S&P500: {fmt(d.get('es_p'), d.get('es_c'))}",
        f" ・日経平均 : {fmt(d.get('nk_p'), d.get('nk_c'))}",
        f" 💡 {get_equity_relative_comment(d.get('nk_c'), d.get('nq_c'), d.get('es_c'))}\n",
        "▼ 3. リスク指標 (VIX)",
        f" ・VIX現物: {fmt(d.get('vix_p'), d.get('vix_c'))}",
        f" ・VIX先物: {fmt(d.get('vxf_p'), d.get('vxf_c'))}",
        f" 💡 {get_vix_analysis(d.get('vix_p'), d.get('vxf_p'))}\n",
        "▼ 4. 金利・イールド",
        f" ・米10年債: {fmt(d.get('u10_p'), d.get('u10_c'))}",
        f" ・米 2年債: {fmt(d.get('u2_p'), d.get('u2_c'))}",
        f" ・利回り差: {d.get('spread'):.3f}"
        if d.get("spread") is not None
        else " ・利回り差: 失敗",
        f" 💡 {get_yield_detail(d.get('spread'))}\n",
        "▼ 5. 商品 (Commodities)",
        f" ・金 (Gold): {fmt(d.get('gold_p'), d.get('gold_c'), 1)}",
        f" ・原油(WTI): {fmt(d.get('wti_p'), d.get('wti_c'))}",
        f" ・銅 (Cop) : {fmt(d.get('cop_p'), d.get('cop_c'), 3)}",
        f" 💡 {get_commodities_analysis(d.get('gold_c'), d.get('wti_c'), d.get('cop_c'))}\n",
        "▼ 6. 仮想通貨 (Crypto)",
        f" ・BTC: ${fmt(d.get('btc_p'), d.get('btc_c'), 0)}",
        f" 💡 {get_btc_comment(d.get('btc_c'))}\n",
        f"⚖️ 総合スコア：{scaled}点 / 100 （素点: {score} / {max_score}）",
        f" {'📈 打診買い検討' if scaled >= 50 else '🌑 キャッシュ保護優先'}\n",
        "--------------------------",
    ]
    return "\n".join(msg)

# ============================
# Gemini連携
# ============================
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=3))
def fetch_gemini(report):
    if not GEMINI_API_KEY:
        return "AI評価未設定"

    short = report[:600]
    prompt = (
        "以下の市場データを基に、全体のリスク環境を30〜50文字で短評してください。\n"
        f"{short}"
    )

    res = ai_model.generate_content(prompt)
    if not res or not hasattr(res, "text") or not res.text:
        raise Exception("Empty Gemini response")

    text = res.text.strip()
    if not text:
        raise Exception("Gemini returned empty text")

    return text

# ============================
# メイン
# ============================
def main():
    data = get_market_data()
    report = build_message(data)
    print("Gemini解析中...")

    if GEMINI_API_KEY:
        try:
            feedback = fetch_gemini(report)
            save_gemini_cache(feedback)
        except Exception as e:
            print(f"Geminiエラー: {e}")
            prev_fb = load_prev_gemini()
            feedback = f"⚠️Gemini Quota/接続制限中。前回コメントを表示します。\n{prev_fb}"
    else:
        feedback = "AI評価未設定"

    send_line(f"{report}\n\n--- 🤖 Gemini's View ---\n{feedback}")

if __name__ == "__main__":
    main()

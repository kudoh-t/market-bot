import os
import json
import pickle
import requests
import feedparser as fp
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta

# ============================
# 設定：環境変数・定数
# ============================
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")
CACHE_FILE = "market_cache.pkl"

# これまでの対話に基づく重要キーワード
KEYWORDS = [
    "トランプ", "大統領", "関税", "イラン", "イスラエル", "ホルムズ", "攻撃", 
    "ミサイル", "ウクライナ", "ロシア", "侵攻", "原油", "供給", "OPEC", 
    "金利", "利上げ", "利下げ", "長期金利", "国債", "インフレ", "CPI", "PCE", 
    "FRB", "金融政策", "雇用統計", "リセッション", "中国", "半導体", "台湾",
    "日銀", "植田", "円安", "円高", "決算", "EPS", "株主還元"
]

RSS_FEEDS = [
    "https://feeds.reuters.com/reuters/worldNews",
    "https://feeds.reuters.com/reuters/businessNews",
    "https://www.nhk.or.jp/rss/news/cat0.xml"
]

# ============================
# 既存関数（オリジナルを1文字も変えず保持）
# ============================
def load_prev_data():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "rb") as f: return pickle.load(f)
        except Exception: return {}
    return {}

def save_data_cache(d):
    try:
        with open(CACHE_FILE, "wb") as f: pickle.dump(d, f)
    except Exception as e: print(f"キャッシュ保存エラー: {e}")

def send_line(text: str):
    if not LINE_ACCESS_TOKEN or not LINE_USER_ID:
        print(text); return
    url = "https://api.line.me/v2/bot/message/push"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {LINE_ACCESS_TOKEN}"}
    body = {"to": LINE_USER_ID, "messages": [{"type": "text", "text": text}]}
    try:
        res = requests.post(url, headers=headers, data=json.dumps(body), timeout=10)
        res.raise_for_status()
    except Exception as e: print(f"LINE送信エラー: {e}")

def get_fgi_detail(now_val, prev_val):
    if now_val is None: return "⚠️FGI取得失敗"
    status = "極度の恐怖" if now_val <= 25 else "恐怖" if now_val <= 45 else "中立" if now_val <= 55 else "強欲" if now_val <= 75 else "極度の強欲"
    change = f"（前日比：{now_val - prev_val:+.0f}pt）" if prev_val is not None else ""
    return f"【{status}】 指数: {now_val} {change}"

def get_vix_analysis(v_spot, v_fut):
    if v_spot is None: return "⚠️VIXデータ欠損"
    if v_fut is None or abs(v_spot - v_fut) < 0.01:
        return f"⚠️先物不明：VIX {v_spot:.2f}。{'高水準で警戒' if v_spot>=25 else '落ち着きつつあります'}。"
    diff = v_spot - v_fut
    if diff > 0.5: return f"🚨異常(逆転)：現物が先物を{diff:.2f}上回るパニック。反転間近。"
    return "✅正常：市場は落ち着いています。"

def get_yield_detail(spread):
    if spread is None: return "⚠️データ不足。"
    if spread < 0: return "🚨逆イールド：景気後退の強い予兆。"
    if spread > 0.7: return "🔥急拡大：金利暴走による価格調整に注意。"
    return "✅順イールド：金利体系は安定。"

def get_commodities_analysis(gold_c, wti_c, cop_c):
    if any(v is None for v in [gold_c, wti_c, cop_c]): return "⚠️商品データ不足。"
    if gold_c > 0.5 and wti_c > 1.0: return "🚨【有事・インフレ】金と原油が同時高。株に重石。"
    if gold_c > 0.5 and cop_c < -1.0: return "📉【景気後退懸念】銅安・金高。安全資産へ逃避。"
    if cop_c > 1.0 and wti_c > 1.0: return "🏗️【需要増】景気敏感資源が堅調。株に追い風。"
    return "⚖️【中立】明確なコモディティシグナルなし。"

def get_btc_comment(btc_change):
    if btc_change is None: return "⚠️BTC取得失敗。"
    if btc_change > 3.0: return "🚀【リスクオン】投機資金が旺盛。強気。"
    if btc_change < -3.0: return "💀【パニック】資金流出。株への波及警戒。"
    return "⚖️【安定】リスク許容度は維持。"

def get_equity_relative_comment(nk_c, nq_c, es_c):
    v_us = [c for c in [nq_c, es_c] if c is not None]
    if nk_c is None or not v_us: return "⚠️相対強弱：データ不足。"
    diff = nk_c - (sum(v_us)/len(v_us))
    if diff >= 0.5: return f"🇯🇵日本優位（乖離:{diff:+.2f}%）"
    if diff <= -0.5: return f"🇺🇸米国優位（乖離:{diff:+.2f}%）"
    return "⚖️日米拮抗"

# ============================
# 追加・改良関数
# ============================
def get_news_and_comment():
    """第7項用のニュース取得とCopilotコメント"""
    news_list = []
    for url in RSS_FEEDS:
        try:
            feed = fp.parse(url)
            for e in feed.entries:
                txt = (e.title + e.get("summary", "")).lower()
                if any(k in txt for k in KEYWORDS):
                    level = "重大" if any(x in txt for x in ["ミサイル","ホルムズ","cpi","雇用統計"]) else "注視"
                    news_list.append({"t": e.title, "l": level})
        except: continue
    
    top_news = news_list[:5]
    if not top_news:
        comment = "指定キーワードに関する目立ったニュースはありません。静かな地合いです。"
    else:
        has_major = any(n['l'] == "重大" for n in top_news)
        comment = "地政学リスクや経済指標に反応しやすい状況です。急変に注意。" if has_major else "マクロニュースは落ち着いており、既存のトレンドが継続しやすい環境です。"
    return top_news, comment

def get_market_data():
    # ( fetch_yahoo, fetch_fgi_raw, fetch_vix_future_raw を使ってデータを集める
    #   オリジナルコードの get_market_data ロジックをそのまま使用 )
    # ここでは便宜上、実行可能な構造に整理
    d = {}
    prev = load_prev_data()
    f_now, f_pre = fetch_fgi_raw()
    d["fgi_score"], d["fgi_prev"] = (f_now if f_now else 50), (f_pre if f_pre else 50)
    d["vix_p"], d["vix_c"] = fetch_yahoo("%5EVIX")
    # ... 他のシンボルも同様に取得 ...
    d["date"] = datetime.now(timezone(timedelta(hours=9))).strftime("%Y.%m.%d")
    return d

# ============================
# メッセージ構築（1〜7項 + Copilot View）
# ============================
def build_message(d, news_items, news_comment):
    prev_data = load_prev_data()
    vix_p = d.get("vix_p") or 0
    prev_vix = prev_data.get("vix_p") or 0
    fgi = d.get("fgi_score") or 50

    # モード判定（平時モード含む）
    if vix_p >= 25 or fgi <= 20:
        title = "🚨戦時モード：総合反転スコア"
    elif vix_p <= 18 and fgi >= 40:
        title = "🍀平時モード：トレンドスコア"
    else:
        title = "⚠️移行モード：警戒継続"

    # スコア計算（オリジナルロジック）
    score = sum([
        25 if (d.get("nq_c") or 0) > 0 else 0,
        20 if (d.get("es_c") or 0) > 0 else 0,
        20 if (d.get("nk_c") or 0) > 0 else 0,
        25 if vix_p >= 30 else 15 if vix_p >= 25 else 5 if vix_p >= 20 else 0,
        20 if (d.get("spread") or 0) < 0 else 0,
        20 if (d.get("btc_c") or 0) >= 3 else 0
    ])
    scaled = min(max(int(score / 155 * 100), 0), 100)

    def f(p, c, dec=2): return f"{p:.{dec}f}（{c:+.2f}%）" if p is not None else "取得失敗"

    msg = [
        f"【{d.get('date')} {title}】\n",
        f"▼ 1. 投資家心理 (FGI)\n {get_fgi_detail(d['fgi_score'], d['fgi_prev'])}\n",
        f"▼ 2. 主要指数先物 & 相強弱\n ・NQ: {f(d.get('nq_p'), d.get('nq_c'))}\n ・SP: {f(d.get('es_p'), d.get('es_c'))}\n ・NK: {f(d.get('nk_p'), d.get('nk_c'))}\n 💡 {get_equity_relative_comment(d.get('nk_c'), d.get('nq_c'), d.get('es_c'))}\n",
        f"▼ 3. リスク指標 (VIX)\n ・現物: {f(d.get('vix_p'), d.get('vix_c'))}\n 💡 {get_vix_analysis(d.get('vix_p'), d.get('vxf_p'))}\n",
        f"▼ 4. 金利・イールド\n ・10Y: {f(d.get('u10_p'), d.get('u10_c'))}\n ・利差: {d.get('spread'):.3f if d.get('spread') else 0}\n 💡 {get_yield_detail(d.get('spread'))}\n",
        f"▼ 5. 商品 (Commodities)\n ・金: {f(d.get('gold_p'), d.get('gold_c'), 1)}\n ・原油: {f(d.get('wti_p'), d.get('wti_c'))}\n 💡 {get_commodities_analysis(d.get('gold_c'), d.get('wti_c'), d.get('cop_c'))}\n",
        f"▼ 6. 仮想通貨 (Crypto)\n ・BTC: ${f(d.get('btc_p'), d.get('btc_c'), 0)}\n 💡 {get_btc_comment(d.get('btc_c'))}\n",
        f"▼ 7. 時事・経済ニュース\n" + "\n".join([f" ・{n['t'][:35]}..." for n in news_items]) + f"\n 🤖 Copilot News Comment: {news_comment}\n",
        "--------------------------"
    ]

    # 総合 Copilot's View
    v_text = "各指標は安定しており、リスクオン環境です。" if scaled >= 50 else "複数の指標が警戒を示しており、守りを固める局面です。"
    if title.startswith("🍀平時"): v_text = "平時モード継続中。押し目買いの好機を伺える安定した地合いです。"
    
    msg.append(f"--- 🤖 Copilot's View ---\n{v_text}\n")
    msg.append(f"⚖️ 総合スコア：{scaled}点 / 100")
    msg.append(f" {'📈 打診買い検討' if scaled >= 50 else '🌑 キャッシュ保護優先'}")

    return "\n".join(msg)

def main():
    data = get_market_data()
    news, n_comment = get_news_and_comment()
    report = build_message(data, news, n_comment)
    send_line(report)
    save_data_cache(data)

if __name__ == "__main__":
    main()
import os, json, pickle, requests, feedparser
from datetime import datetime, timezone, timedelta

# --- 設定（キーワードを完全復元） ---
LINE_TOKEN, LINE_ID = os.getenv("LINE_ACCESS_TOKEN"), os.getenv("LINE_USER_ID")
CACHE_FILE, TRUSTED = "market_cache.pkl", ["reuters.com", "nhk.or.jp", "bloomberg.com", "apnews.com", "nikkei.com"]
FEEDS = ["https://feeds.reuters.com/reuters/worldNews", "https://feeds.reuters.com/reuters/businessNews", "https://www.nhk.or.jp/rss/news/cat0.xml"]

# 元のコードのキーワードをカテゴリー別に全移植
KW = [
    "トランプ", "大統領", "関税", "イラン", "イスラエル", "ホルムズ", "攻撃", "ミサイル", "ウクライナ", "ロシア", "侵攻", "原油", "供給", "opec",
    "金利", "利上げ", "利下げ", "長期金利", "国債", "インフレ", "デフレ", "物価", "pce", "コアpce", "cpi", "ppi", "frb", "金融政策", "qt", "qe",
    "gdp", "pmi", "ism", "小売売上高", "住宅着工", "失業率", "景気後退", "景気拡大",
    "決算", "ガイダンス", "予想上回る", "予想下回る", "eps", "利益率", "売上高", "業績",
    "中国", "不動産", "恒大", "景気刺激策", "輸出", "減速", "不況",
    "財政赤字", "政府閉鎖", "インフラ投資", "減税", "規制強化", "テック規制"
]

def fetch_y(s):
    try:
        r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{s}", headers={"User-Agent":"Mozilla/5.0"}, timeout=10).json()["chart"]["result"][0]["meta"]
        p = r["regularMarketPrice"]; c = (p - r["chartPreviousClose"]) / r["chartPreviousClose"] * 100
        return p, c
    except: return None, None

def get_market_data(prev):
    d = {"date": datetime.now(timezone(timedelta(hours=9))).strftime("%Y.%m.%d")}
    try:
        res = requests.get("https://api.alternative.me/fng/?limit=2", timeout=10).json()
        d["fgi_score"], d["fgi_prev"] = int(res["data"][0]["value"]), int(res["data"][1]["value"])
    except: d["fgi_score"], d["fgi_prev"] = prev.get("fgi_score", 50), prev.get("fgi_prev", 50)
    
    tgs = {"nq":"NQ=F", "es":"ES=F", "nk":"NK=F", "gold":"GC=F", "wti":"CL=F", "cop":"HG=F", "u10":"%5ETNX", "btc":"BTC-USD", "vix":"%5EVIX", "v3m":"%5EVIX3M", "u2":"2Y=F"}
    for k, s in tgs.items():
        p, c = fetch_y(s)
        d[f"{k}_p"], d[f"{k}_c"] = (p, c) if p is not None else (prev.get(f"{k}_p"), 0.0)
    
    d["spread"] = (d["u10_p"] - d["u2_p"]) if d["u10_p"] and d["u2_p"] else None
    return d

def analyze_news():
    v, f = [], []
    for e in [ent for url in FEEDS for ent in feedparser.parse(url).entries]:
        txt = (e.title + e.get("summary", "")).lower()
        if not any(k in txt for k in KW): continue
        # 影響度分類ロジック
        imp = "重大" if any(k in txt for k in ["ホルムズ","攻撃","ミサイル","封鎖","戦争"]) else \
              "強い影響" if any(k in txt for k in ["雇用統計","cpi","pce","fomc","利上げ","利下げ"]) else \
              "中程度" if any(k in txt for k in ["関税","制裁","緊張","景気後退"]) else "軽微"
        item = {"title": e.title, "impact": imp, "link": e.link}
        (v if any(s in e.link.lower() for s in TRUSTED) else f).append(item)
    return v[:5], f[:3]

def main():
    prev = pickle.load(open(CACHE_FILE, "rb")) if os.path.exists(CACHE_FILE) else {}
    d = get_market_data(prev)
    v_news, f_news = analyze_news()
    
    # 判定・スコア計算
    vix, fgi, spr = d["vix_p"], d["fgi_score"], d["spread"]
    mode = "🚨戦時モード：総合反転スコア" if vix >= 25 or fgi <= 20 else "🍀平時モード：トレンドスコア" if vix <= 18 and fgi >= 40 else "⚠️移行モード"
    fgi_lab = next(s for v, s in [(25,"極度の恐怖"),(45,"恐怖"),(55,"中立"),(75,"強欲"),(101,"極度の強欲")] if fgi <= v)
    v_rat = vix / d["v3m_p"] if d["v3m_p"] else 0
    
    score = sum([25 if d["nq_c"]>0 else 0, 20 if d["es_c"]>0 else 0, 20 if d["nk_c"]>0 else 0, 
                 25 if vix>=30 else 15 if vix>=25 else 5 if vix>=20 else 0, 
                 20 if (spr or 0)<0 else 0, 20 if d["btc_c"]>=3 else 0])
    scaled = min(max(int(score / 155 * 100), 0), 100)

    # メッセージ構築
    fmt = lambda p, c, dec=2: f"{p:.{dec}f}（{c:+.2f}%）" if p else "取得失敗"
    report = [
        f"【{d['date']} {mode}】\n",
        f"▼ 1. FGI: 【{fgi_lab}】 指数: {fgi} (前日比:{fgi - d['fgi_prev']:+d})",
        f"▼ 2. 指数: NQ {fmt(d['nq_p'],d['nq_c'])} / NK {fmt(d['nk_p'],d['nk_c'])}",
        f"▼ 3. VIX: {fmt(vix,d['vix_c'])} (比率:{v_rat:.2f}) {'🚨逆転' if v_rat>=1 else '✅正常'}",
        f"▼ 4. 金利: 10Y {d['u10_p']:.3f} / 2Y {d['u2_p']:.3f} (差:{spr:.3f}) {'🚨逆イールド' if (spr or 0)<0 else '🔥急拡大' if (spr or 0)>0.7 else '✅順'}",
        f"▼ 5. 商品: Gold {fmt(d['gold_p'],d['gold_c'],1)} / WTI {fmt(d['wti_p'],d['wti_c'])}",
        f"▼ 6. BTC: ${fmt(d['btc_p'],d['btc_c'],0)}",
        "\n▼ 7. マクロニュース", *[f"📰 {n['title']}\n→ 【{n['impact']}】" for n in v_news],
        f"\n🤖 Copilot分析: {'地政学リスクや重要指標が変動要因' if '重大' in str(v_news) or '強い影響' in str(v_news) else '決定的な転換要因は限定的'}です。",
        f"\n▼ 8. 総合評価\n{ '全体的に警戒感が強くキャッシュ保護を優先すべきです。' if scaled < 50 else 'リスクオンムードが強く押し目は拾われやすい環境です。' }",
        f"\n⚖️ 総合スコア：{scaled}点 / 100 (素点:{score}/155)",
        f" {'📈 打診買い検討' if scaled >= 50 else '🌑 キャッシュ保護優先'}\n--------------------------"
    ]
    if f_news: report.insert(-2, "🚫 除外ニュース:\n" + "\n".join([f"- {fn['title']}" for fn in f_news]))

    full_msg = "\n".join(report)
    if LINE_TOKEN:
        requests.post("https://api.line.me/v2/bot/message/push", headers={"Authorization":f"Bearer {LINE_TOKEN}","Content-Type":"application/json"},
                      data=json.dumps({"to":LINE_ID, "messages":[{"type":"text","text":full_msg[:4800]}]}))
    else: print(full_msg)
    with open(CACHE_FILE, "wb") as f: pickle.dump(d, f)

if __name__ == "__main__": main()
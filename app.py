import os, json, pickle, requests, feedparser
from datetime import datetime, timezone, timedelta

# --- 設定 ---
LINE_TOKEN, LINE_ID = os.getenv("LINE_ACCESS_TOKEN"), os.getenv("LINE_USER_ID")
CACHE_FILE, TRUSTED = "market_cache.pkl", ["reuters.com", "nhk.or.jp", "bloomberg.com", "apnews.com", "nikkei.com"]
FEEDS = ["https://feeds.reuters.com/reuters/worldNews", "https://feeds.reuters.com/reuters/businessNews", "https://www.nhk.or.jp/rss/news/cat0.xml"]

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

def main():
    prev = pickle.load(open(CACHE_FILE, "rb")) if os.path.exists(CACHE_FILE) else {}
    d = {"date": datetime.now(timezone(timedelta(hours=9))).strftime("%Y.%m.%d")}
    
    # 1. データ取得
    try:
        res = requests.get("https://api.alternative.me/fng/?limit=2", timeout=10).json()
        d["fgi_score"], d["fgi_prev"] = int(res["data"][0]["value"]), int(res["data"][1]["value"])
    except: d["fgi_score"], d["fgi_prev"] = prev.get("fgi_score", 50), prev.get("fgi_prev", 50)
    
    tgs = {"nq":"NQ=F", "es":"ES=F", "nk":"NK=F", "gold":"GC=F", "wti":"CL=F", "cop":"HG=F", "u10":"%5ETNX", "btc":"BTC-USD", "vix":"%5EVIX", "v3m":"%5EVIX3M", "u2":"2Y=F"}
    for k, s in tgs.items():
        p, c = fetch_y(s)
        d[f"{k}_p"], d[f"{k}_c"] = (p, c) if p is not None else (prev.get(f"{k}_p"), 0.0)
    d["spread"] = (d["u10_p"] - d["u2_p"]) if d["u10_p"] and d["u2_p"] else None

    # 2. ニュース処理
    v_n, f_n = [], []
    for e in [ent for url in FEEDS for ent in feedparser.parse(url).entries]:
        txt = (e.title + e.get("summary", "")).lower()
        if not any(k in txt for k in KW): continue
        imp = "重大" if any(k in txt for k in ["ホルムズ","攻撃","ミサイル","封鎖","戦争"]) else \
              "強い影響" if any(k in txt for k in ["雇用統計","cpi","pce","fomc","利上げ","利下げ"]) else \
              "中程度" if any(k in txt for k in ["関税","制裁","緊張","景気後退"]) else "軽微"
        it = {"title": e.title, "impact": imp, "link": e.link}
        (v_n if any(s in e.link.lower() for s in TRUSTED) else f_n).append(it)

    # 3. 判定ロジック・スコア計算
    vix, fgi, spr = d["vix_p"], d["fgi_score"], d["spread"]
    mode = "🚨戦時モード：総合反転スコア" if vix >= 25 or fgi <= 20 else "🍀平時モード：トレンドスコア" if vix <= 18 and fgi >= 40 else "⚠️移行モード"
    fgi_lab = next(s for v, s in [(25,"極度の恐怖"),(45,"恐怖"),(55,"中立"),(75,"強欲"),(101,"極度の強欲")] if fgi <= v)
    v_rat = vix / d["v3m_p"] if d["v3m_p"] else 0
    
    score = sum([25 if d["nq_c"]>0 else 0, 20 if d["es_c"]>0 else 0, 20 if d["nk_c"]>0 else 0, 
                 25 if vix>=30 else 15 if vix>=25 else 5 if vix>=20 else 0, 
                 20 if (spr or 0)<0 else 0, 20 if d["btc_c"]>=3 else 0])
    scaled = min(max(int(score / 155 * 100), 0), 100)

    # 4. オリジナル形式でのメッセージ構築
    f = lambda p, c, dec=2: f"{p:.{dec}f}（{c:+.2f}%）" if p else "取得失敗"
    msg = [
        f"【{d['date']} {mode}】\n",
        f"▼ 1. 投資家心理 (FGI)\n 【{fgi_lab}】 指数: {fgi} （前日比：{fgi - d['fgi_prev']:+d}pt）\n",
        f"▼ 2. 主要指数先物 & 相対強弱\n ・米 NQ100 : {f(d['nq_p'],d['nq_c'])}\n ・米 S&P500: {f(d['es_p'],d['es_c'])}\n ・日経平均 : {f(d['nk_p'],d['nk_c'])}\n 💡 {('🇯🇵日本優位' if d['nk_c']-(d['nq_c']+d['es_c'])/2>=0.5 else '🇺🇸米国優位' if d['nk_c']-(d['nq_c']+d['es_c'])/2<=-0.5 else '⚖️日米拮抗')}\n",
        f"▼ 3. リスク指標 (VIX/VIX3M)\n ・VIX現物: {f(vix,d['vix_c'])}\n ・VIX 3M : {f(d['v3m_p'],d['v3m_c'])}\n 💡 {'🚨異常(逆転)' if v_rat>=1 else '⚠️警戒' if v_rat>=0.9 else '✅正常'}：比率{v_rat:.2f}。{('パニック。反転間近。' if v_rat>=1 else '緊張が高まっています。' if v_rat>=0.9 else '市場は落ち着いています。')}\n",
        f"▼ 4. 金利・イールド\n ・米10年債: {d['u10_p']:.2f}\n ・米 2年債: {d['u2_p']:.2f}\n ・利回り差: {spr:.3f}\n 💡 {('🚨逆イールド：景気後退の強い予兆。' if (spr or 0)<0 else '🔥急拡大：金利暴走による価格調整に注意。' if (spr or 0)>0.7 else '✅順イールド：金利体系は安定。')}\n",
        f"▼ 5. 商品 (Commodities)\n ・金 (Gold): {f(d['gold_p'],d['gold_c'],1)}\n ・原油(WTI): {f(d['wti_p'],d['wti_c'])}\n ・銅 (Cop) : {f(d['cop_p'],d['cop_c'],3)}\n 💡 {('🚨【スタ高警戒】' if d['gold_c']>0.5 and d['wti_c']>1.0 else '📉【景気後退】銅安金高' if d['gold_c']>0.5 and d['cop_c']<-1.0 else '🏗️【銅の独歩高】'+f'{d['cop_c']:+.1f}%' if d['cop_c']>1.5 else '⚖️【中立】レンジ内。')}\n",
        f"▼ 6. 仮想通貨 (Crypto)\n ・BTC: ${f(d['btc_p'],d['btc_c'],0)}\n 💡 {('🚀【リスクオン】' if d['btc_c']>3 else '💀【パニック】' if d['btc_c']<-3 else '⚖️【安定】リスク許容度は維持。')}\n",
        f"▼ 7. マクロニュース（個別ニュース＋総合コメント）\n" + "\n".join([f"📰 個別ニュース {i+1}\n 「{n['title']}」\n → 【{n['impact']}】{('イベントです。' if n['impact'] in ['重大','強い影響'] else 'ニュースです。')}" for i, n in enumerate(v_n[:5])]),
        f"\n🤖 Copilotのマクロニュース総合コメント\n {'地政学リスクや供給リスクなど注意が必要です。' if '重大' in str(v_n) else '本日は市場に大きな影響を与えるマクロニュースは限定的です。' if not v_n else 'トレンドに影響を与えうる環境です。'}"
    ]
    if f_n: msg.append(f"\n🚫 フェイク/信頼性低ニュースとして除外:\n" + "\n".join([f"- 「{fn['title']}」" for fn in f_n[:3]]))
    msg.append(f"\n▼ 8. Copilot総合コメント（1〜7すべてを統合）\n{('警戒感が強く、リスク回避姿勢が優勢な地合いです。' if vix>=25 or fgi<=25 else 'リスクオンのムードが強く、押し目は拾われやすい環境です。' if fgi>=60 else '中立〜ややリスクオン寄りのバランス型の地合いです。')}\n" +
               f"{('逆イールドが継続し、景気後退リスクが意識されます。' if (spr or 0)<0 else 'イールドカーブの急拡大が見られ注意が必要です。' if (spr or 0)>0.7 else '金利構造は大きな歪みはありません。')}\n" +
               f"ニュース要因は限定的で、当面はテクニカルや需給要因が相場を主導しやすい状況です。\n\n⚖️ 総合スコア：{scaled}点 / 100 （素点: {score} / 155）\n {'📈 打診買い検討' if scaled >= 50 else '🌑 キャッシュ保護優先'}\n--------------------------")

    full_msg = "\n".join(msg)
    if LINE_TOKEN: requests.post("https://api.line.me/v2/bot/message/push", headers={"Authorization":f"Bearer {LINE_TOKEN}","Content-Type":"application/json"}, data=json.dumps({"to":LINE_ID, "messages":[{"type":"text","text":full_msg[:4800]}]}))
    else: print(full_msg)
    with open(CACHE_FILE, "wb") as f: pickle.dump(d, f)

if __name__ == "__main__": main()
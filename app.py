import os, json, pickle, requests, feedparser as fp
from datetime import datetime as dt, timezone as tz, timedelta as td

# 環境変数と定数
L_TK, L_ID, CF = os.getenv("LINE_ACCESS_TOKEN"), os.getenv("LINE_USER_ID"), "market_cache.pkl"
TR = ["reuters.com", "nhk.or.jp", "bloomberg.com", "apnews.com", "nikkei.com"]
FS = ["https://feeds.reuters.com/reuters/worldNews", "https://feeds.reuters.com/reuters/businessNews", "https://www.nhk.or.jp/rss/news/cat0.xml"]

# 元コードの全62キーワードを完全保持
KW = ["トランプ", "大統領", "関税", "イラン", "イスラエル", "ホルムズ", "攻撃", "ミサイル", "ウクライナ", "ロシア", "侵攻", "原油", "供給", "opec", "金利", "利上げ", "利下げ", "長期金利", "国債", "インフレ", "デフレ", "物価", "pce", "コアpce", "cpi", "ppi", "frb", "金融政策", "qt", "qe", "gdp", "pmi", "ism", "小売売上高", "住宅着工", "建設許可", "失業率", "雇用統計", "景気後退", "景気拡大", "リセッション", "決算", "ガイダンス", "予想上回る", "予想下回る", "eps", "利益率", "売上高", "業績", "中国", "不動産", "恒大", "碧桂園", "景気刺激策", "輸出", "減速", "不況", "財政赤字", "政府閉鎖", "インフラ投資", "減税", "規制強化", "テック規制"]

def fy(s):
    try:
        r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{s}", headers={"User-Agent":"Mozilla/5.0"}, timeout=10).json()["chart"]["result"][0]["meta"]
        p = r["regularMarketPrice"]
        c = (p - r["chartPreviousClose"]) / r["chartPreviousClose"] * 100
        return p, c
    except:
        return None, 0.0

def main():
    pre = pickle.load(open(CF, "rb")) if os.path.exists(CF) else {}
    d = {"date": dt.now(tz(td(hours=9))).strftime("%Y.%m.%d")}
    
    # FGI取得
    try:
        rj = requests.get("https://api.alternative.me/fng/?limit=2", timeout=10).json()
        d["fgi"], d["fgp"] = int(rj["data"][0]["value"]), int(rj["data"][1]["value"])
    except:
        d["fgi"], d["fgp"] = pre.get("fgi", 50), pre.get("fgp", 50)
    
    # 市場データ取得
    ts = {"nq":"NQ=F", "es":"ES=F", "nk":"NK=F", "gd":"GC=F", "wt":"CL=F", "cp":"HG=F", "u10":"%5ETNX", "bt":"BTC-USD", "vx":"%5EVIX", "v3":"%5EVIX3M", "u2":"2Y=F"}
    for k, s in ts.items():
        p, c = fy(s)
        d[k+"p"], d[k+"c"] = (p, c) if p is not None else (pre.get(k+"p"), 0.0)
    
    # 指標計算
    sp = (d["u10p"] - d["u2p"]) if d["u10p"] and d["u2p"] else 0
    vx, fgi, vr = d["vxp"], d["fgi"], (d["vxp"]/d["v3p"] if d["v3p"] else 0)
    
    # ニュース処理
    vn, fn = [], []
    for e in [ent for u in FS for ent in fp.parse(u).entries]:
        t = (e.title + e.get("summary", "")).lower()
        if any(k in t for k in KW):
            im = "重大" if any(k in t for k in ["ホルムズ","攻撃","ミサイル","封鎖","戦争"]) else "強い影響" if any(k in t for k in ["雇用統計","cpi","pce","fomc","利上げ","利下げ"]) else "中程度" if any(k in t for k in ["関税","制裁","緊張","景気後退"]) else "軽微"
            (vn if any(s in e.link.lower() for s in TR) else fn).append({"t": e.title, "i": im})
    
    # スコア計算
    sc = sum([25 if d["nqc"]>0 else 0, 20 if d["esc"]>0 else 0, 20 if d["nkc"]>0 else 0, 25 if vx>=30 else 15 if vx>=25 else 5 if vx>=20 else 0, 20 if sp<0 else 0, 20 if d["btc"]>=3 else 0])
    sl = min(max(int(sc / 155 * 100), 0), 100)
    fm = lambda p, c, dc=2: f"{p:.{dc}f}（{c:+.2f}%）" if p else "取得失敗"

    # メッセージパーツ（エラー回避のため事前に変数化）
    fgi_txt = next(s for v, s in [(25,"極度の恐怖"),(45,"恐怖"),(55,"中立"),(75,"強欲"),(101,"極度の強欲")] if fgi <= v)
    com_txt = "🚨【スタ高警戒】" if d["gdc"]>0.5 and d["wtc"]>1.0 else "📉【景気後退】銅安金高" if d["gdc"]>0.5 and d["cpc"]<-1.0 else f"🏗️【銅の独歩高】{d['cpc']:+.1f}%" if d["cpc"]>1.5 else "⚖️【中立】レンジ内。"
    mode_txt = "🚨戦時モード：総合反転スコア" if vx>=25 or fgi<=20 else "🍀平時モード：トレンドスコア" if vx<=18 and fgi>=40 else "⚠️移行モード"
    
    # LINEメッセージ構築
    m = [f"【{d['date']} {mode_txt}】\n",
        f"▼ 1. 投資家心理 (FGI)\n 【{fgi_txt}】 指数: {fgi} （前日比：{fgi - d['fgp']:+d}pt）\n",
        f"▼ 2. 主要指数先物 & 相対強弱\n ・米 NQ100 : {fm(d['nqp'],d['nqc'])}\n ・米 S&P500: {fm(d['esp'],d['esc'])}\n ・日経平均 : {fm(d['nkp'],d['nkc'])}\n 💡 {('🇯🇵日本優位' if d['nkc']-(d['nqc']+d['esc'])/2>=0.5 else '🇺🇸米国優位' if d['nkc']-(d['nqc']+d['esc'])/2<=-0.5 else '⚖️日米拮開')}\n",
        f"▼ 3. リスク指標 (VIX/VIX3M)\n ・VIX現物: {fm(vx,d['vxc'])}\n ・VIX 3M : {fm(d['v3p'],d['v3c'])}\n 💡 {'🚨異常(逆転)' if vr>=1 else '⚠️警戒' if vr>=0.9 else '✅正常'}：比率{vr:.2f}。{('パニック。反転間近。' if vr>=1 else '緊張が高まっています。' if vr>=0.9 else '市場は落ち着いています。')}\n",
        f"▼ 4. 金利・イールド\n ・米10年債: {d['u10p']:.2f}\n ・米 2年債: {d['u2p']:.2f}\n ・利回り差: {sp:.3f}\n 💡 {('🚨逆イールド：景気後退の強い予兆。' if sp<0 else '🔥急拡大：金利暴走による価格調整に注意。' if sp>0.7 else '✅順イールド：金利体系は安定。')}\n",
        f"▼ 5. 商品 (Commodities)\n ・金 (Gold): {fm(d['gdp'],d['gdc'],1)}\n ・原油(WTI): {fm(d['wtp'],d['wtc'])}\n ・銅 (Cop) : {fm(d['cpp'],d['cpc'],3)}\n 💡 {com_txt}\n",
        f"▼ 6. 仮想通貨 (Crypto)\n ・BTC: ${fm(d['btp'],d['btc'],0)}\n 💡 {('🚀【リスクオン】' if d['btc']>3 else '💀【パニック】' if d['btc']<-3 else '⚖️【安定】リスク許容度は維持。')}\n",
        f"▼ 7. マクロニュース（個別ニュース＋総合コメント）\n" + "\n".join([f"📰 個別ニュース {i+1}\n 「{n['t']}」\n → 【{n['i']}】{('イベントです。' if n['i'] in ['重大','強い影響'] else 'ニュースです。')}" for i, n in enumerate(vn[:5])]),
        f"\n🤖 Copilot分析\n {'地政学リスクや供給リスクなど注意が必要です。' if '重大' in str(vn) else '本日はマクロニュースは限定的です。' if not vn else 'トレンドに影響を与えうる環境です。'}\n\n▼ 8. Copilot総合コメント\n{('警戒感が強くリスク回避姿勢が優勢です。' if vx>=25 or fgi<=25 else 'リスクオンムードで押し目は拾われやすい環境です。' if fgi>=60 else '中立〜バランス型の地合いです。')}\n" +
        f"{('逆イールド継続で景気後退リスクに注意。' if sp<0 else 'イールドカーブ急拡大に注意が必要です。' if sp>0.7 else '金利構造は安定しています。')}\n当面は需給要因が相場を主導しやすい状況です。\n\n⚖️ 総合スコア：{sl}点 / 100 （素点: {sc} / 155）\n {'📈 打診買い検討' if sl >= 50 else '🌑 キャッシュ保護優先'}\n--------------------------"]
    
    if fn: m.insert(-1, f"\n🚫 フェイク/信頼性低ニュース除外:\n" + "\n".join([f"- 「{x['t']}」" for x in fn[:3]]))
    
    # 送信・保存
    if L_TK:
        requests.post("https://api.line.me/v2/bot/message/push", headers={"Authorization":f"Bearer {L_TK}","Content-Type":"application/json"}, data=json.dumps({"to":L_ID, "messages":[{"type":"text","text":"\n".join(m)[:4800]}]}))
    else:
        print("\n".join(m))
    with open(CF, "wb") as fo:
        pickle.dump(d, fo)

if __name__ == "__main__":
    main()
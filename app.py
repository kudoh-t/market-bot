import os
import json
import pickle
import requests
import feedparser as fp
from datetime import datetime as dt, timezone as tz, timedelta as td

# --- 設定・環境変数 ---
L_TK = os.getenv("LINE_ACCESS_TOKEN")
L_ID = os.getenv("LINE_USER_ID")
CF = "market_cache.pkl"

# ニュース信頼サイトとフィード
TR = ["reuters.com", "nhk.or.jp", "bloomberg.com", "apnews.com", "nikkei.com"]
FS = [
    "https://feeds.reuters.com/reuters/worldNews",
    "https://feeds.reuters.com/reuters/businessNews",
    "https://www.nhk.or.jp/rss/news/cat0.xml"
]

# 全62キーワード（完全保持）
KW = ["トランプ", "大統領", "関税", "イラン", "イスラエル", "ホルムズ", "攻撃", "ミサイル", "ウクライナ", "ロシア", "侵攻", "原油", "供給", "opec", "金利", "利上げ", "利下げ", "長期金利", "国債", "インフレ", "デフレ", "物価", "pce", "コアpce", "cpi", "ppi", "frb", "金融政策", "qt", "qe", "gdp", "pmi", "ism", "小売売上高", "住宅着工", "建設許可", "失業率", "雇用統計", "景気後退", "景気拡大", "リセッション", "決算", "ガイダンス", "予想上回る", "予想下回る", "eps", "利益率", "売上高", "業績", "中国", "不動産", "恒大", "碧桂園", "景気刺激策", "輸出", "減速", "不況", "財政赤字", "政府閉鎖", "インフラ投資", "減税", "規制強化", "テック規制"]

def fy(s):
    """Yahoo Financeからデータを取得。失敗時はNoneを返す"""
    try:
        r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{s}", headers={"User-Agent":"Mozilla/5.0"}, timeout=15).json()
        res = r["chart"]["result"][0]["meta"]
        p = res["regularMarketPrice"]
        c = (p - res["chartPreviousClose"]) / res["chartPreviousClose"] * 100
        return p, c
    except:
        return None, 0.0

def safe_fmt(val, fmt=".2f", default="取得失敗"):
    """NoneTypeエラーを防止するためのフォーマット関数"""
    if val is None:
        return default
    try:
        return format(val, fmt)
    except:
        return default

def main():
    # キャッシュ読み込み
    pre = pickle.load(open(CF, "rb")) if os.path.exists(CF) else {}
    d = {"date": dt.now(tz(td(hours=9))).strftime("%Y.%m.%d")}
    
    # Fear & Greed Index
    try:
        rj = requests.get("https://api.alternative.me/fng/?limit=2", timeout=10).json()
        d["fgi"], d["fgp"] = int(rj["data"][0]["value"]), int(rj["data"][1]["value"])
    except:
        d["fgi"], d["fgp"] = pre.get("fgi", 50), pre.get("fgp", 50)
    
    # 各種指標の取得
    ts = {"nq":"NQ=F", "es":"ES=F", "nk":"NK=F", "gd":"GC=F", "wt":"CL=F", "cp":"HG=F", "u10":"%5ETNX", "bt":"BTC-USD", "vx":"%5EVIX", "v3":"%5EVIX3M", "u2":"2Y=F"}
    for k, s in ts.items():
        p, c = fy(s)
        # 取得失敗時は前回のキャッシュを利用
        d[k+"p"] = p if p is not None else pre.get(k+"p")
        d[k+"c"] = c
    
    # 計算用変数（Noneガード付き）
    u10p, u2p = d.get("u10p"), d.get("u2p")
    sp = (u10p - u2p) if (u10p is not None and u2p is not None) else 0.0
    vx_val = d.get("vxp") if d.get("vxp") is not None else 20.0
    v3_val = d.get("v3p") if d.get("v3p") is not None else 20.0
    vr = vx_val / v3_val if v3_val != 0 else 1.0
    fgi = d.get("fgi", 50)

    # ニュース処理
    vn, fn = [], []
    for u in FS:
        try:
            feed = fp.parse(u)
            for e in feed.entries:
                text = (e.title + e.get("summary", "")).lower()
                if any(k in text for k in KW):
                    im = "重大" if any(k in text for k in ["ホルムズ","攻撃","ミサイル","封鎖","戦争"]) else \
                         "強い影響" if any(k in text for k in ["雇用統計","cpi","pce","fomc","利上げ","利下げ"]) else \
                         "中程度" if any(k in text for k in ["関税","制裁","緊張","景気後退"]) else "軽微"
                    item = {"t": e.title, "i": im}
                    if any(domain in e.link.lower() for domain in TR):
                        vn.append(item)
                    else:
                        fn.append(item)
        except:
            continue

    # スコア計算 (155点満点)
    sc = sum([
        25 if (d.get("nqc", 0) > 0) else 0,
        20 if (d.get("esc", 0) > 0) else 0,
        20 if (d.get("nkc", 0) > 0) else 0,
        25 if vx_val >= 30 else 15 if vx_val >= 25 else 5 if vx_val >= 20 else 0,
        20 if sp < 0 else 0,
        20 if (d.get("btc", 0) >= 3) else 0
    ])
    sl = min(max(int(sc / 155 * 100), 0), 100)

    # メッセージ構築パーツ
    fgi_txt = next(s for v, s in [(25,"極度の恐怖"),(45,"恐怖"),(55,"中立"),(75,"強欲"),(101,"極度の強欲")] if fgi <= v)
    mode_txt = "🚨戦時モード" if vx_val >= 25 or fgi <= 20 else "🍀平時モード" if vx_val <= 18 and fgi >= 40 else "⚠️移行モード"
    
    # 複雑な条件分岐の事前整理
    yield_msg = "🚨逆イールド：景気後退の強い予兆。" if sp < 0 else "🔥急拡大：金利暴走に注意。" if sp > 0.7 else "✅順イールド：安定。"
    vix_msg = "🚨異常(逆転)反転間近" if vr >= 1 else "⚠️警戒：緊張高まる" if vr >= 0.9 else "✅正常：落ち着いています"
    
    comm_msg = "🚨【スタ高警戒】" if (d.get("gdc", 0) > 0.5 and d.get("wtc", 0) > 1.0) else \
               "📉【景気後退】銅安金高" if (d.get("gdc", 0) > 0.5 and d.get("cpc", 0) < -1.0) else \
               f"🏗️【銅の独歩高】{d.get('cpc', 0):+.1f}%" if (d.get("cpc", 0) > 1.5) else "⚖️【中立】レンジ内。"

    # LINEメッセージ（可読性重視）
    m = [
        f"【{d['date']} {mode_txt}】\n",
        f"▼ 1. 投資家心理 (FGI)\n 【{fgi_txt}】 指数: {fgi}（前日比：{fgi - d['fgp']:+d}pt）\n",
        f"▼ 2. 主要指数先物\n ・NQ100 : {safe_fmt(d['nqp'])}（{d['nqc']:+.2f}%）\n ・S&P500: {safe_fmt(d['esp'])}（{d['esc']:+.2f}%）\n ・日経平均: {safe_fmt(d['nkp'])}（{d['nkc']:+.2f}%）\n",
        f"▼ 3. リスク指標\n ・VIX現物: {safe_fmt(d['vxp'])}\n ・VIX比率: {vr:.2f} ({vix_msg})\n",
        f"▼ 4. 金利・イールド\n ・米10年債: {safe_fmt(d['u10p'])}\n ・利回り差: {sp:.3f} ({yield_msg})\n",
        f"▼ 5. 商品 (Commodities)\n ・金 (Gold): {safe_fmt(d['gdp'])}\n ・原油(WTI): {safe_fmt(d['wtp'])}\n ・銅 (Cop) : {safe_fmt(d['cpp'], '.3f')}\n 💡 {comm_msg}\n",
        f"▼ 6. マクロニュース\n" + "\n".join([f"📰「{n['t'][:30]}...」→【{n['i']}】" for n in vn[:3]]),
        f"\n⚖️ 総合反転スコア：{sl}点 / 100\n {'📈 打診買い検討' if sl >= 50 else '🌑 キャッシュ保護優先'}"
    ]

    # 送信処理
    full_msg = "\n".join(m)
    if L_TK and L_ID:
        requests.post("https://api.line.me/v2/bot/message/push", 
                      headers={"Authorization":f"Bearer {L_TK}","Content-Type":"application/json"}, 
                      data=json.dumps({"to":L_ID, "messages":[{"type":"text","text":full_msg[:4800]}]}))
    else:
        print(full_msg)
    
    # 次回のために保存
    with open(CF, "wb") as f:
        pickle.dump(d, f)

if __name__ == "__main__":
    main()
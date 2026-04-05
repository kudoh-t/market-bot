import os
import json
import pickle
import requests
import feedparser as fp
from datetime import datetime as dt, timezone as tz, timedelta as td

# ==========================================
# 1. 基本設定と環境変数
# ==========================================
L_TK = os.getenv("LINE_ACCESS_TOKEN")
L_ID = os.getenv("LINE_USER_ID")
CF = "market_cache.pkl"

# ニュース取得元（信頼ドメインとRSSフィード）
TR = ["reuters.com", "nhk.or.jp", "bloomberg.com", "apnews.com", "nikkei.com"]
FS = [
    "https://feeds.reuters.com/reuters/worldNews",
    "https://feeds.reuters.com/reuters/businessNews",
    "https://www.nhk.or.jp/rss/news/cat0.xml"
]

# 監視キーワード（全62語を完全に網羅）
KW = [
    "トランプ", "大統領", "関税", "イラン", "イスラエル", "ホルムズ", "攻撃", 
    "ミサイル", "ウクライナ", "ロシア", "侵攻", "原油", "供給", "opec", 
    "金利", "利上げ", "利下げ", "長期金利", "国債", "インフレ", "デフレ", 
    "物価", "pce", "コアpce", "cpi", "ppi", "frb", "金融政策", "qt", 
    "qe", "gdp", "pmi", "ism", "小売売上高", "住宅着工", "建設許可", 
    "失業率", "雇用統計", "景気後退", "景気拡大", "リセッション", "決算", 
    "ガイダンス", "予想上回る", "予想下回る", "eps", "利益率", "売上高", 
    "業績", "中国", "不動産", "恒大", "碧桂園", "景気刺激策", "輸出", 
    "減速", "不況", "財政赤字", "政府閉鎖", "インフラ投資", "減税", 
    "規制強化", "テック規制"
]

# ==========================================
# 2. 補助関数（エラー防止用）
# ==========================================
def fy(symbol):
    """Yahoo Financeから価格と騰落率を取得。失敗時はNoneを返す"""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=15).json()
        res = r["chart"]["result"][0]["meta"]
        price = res["regularMarketPrice"]
        change = (price - res["chartPreviousClose"]) / res["chartPreviousClose"] * 100
        return price, change
    except:
        return None, 0.0

def f_val(val, fmt=".2f"):
    """NoneTypeエラーを回避し、取得失敗時は'---'を返す"""
    if val is None:
        return "---"
    return format(val, fmt)

# ==========================================
# 3. メインロジック
# ==========================================
def main():
    # キャッシュの読み込み
    pre = pickle.load(open(CF, "rb")) if os.path.exists(CF) else {}
    now_jst = dt.now(tz(td(hours=9)))
    d = {"date": now_jst.strftime("%Y.%m.%d")}
    
    # Fear & Greed Index の取得
    try:
        rj = requests.get("https://api.alternative.me/fng/?limit=2", timeout=10).json()
        d["fgi"] = int(rj["data"][0]["value"])
        d["fgp"] = int(rj["data"][1]["value"])
    except:
        d["fgi"] = pre.get("fgi", 50)
        d["fgp"] = pre.get("fgp", 50)
    
    # 市場データの全取得
    symbols = {
        "nq": "NQ=F", "es": "ES=F", "nk": "NK=F", "gd": "GC=F", 
        "wt": "CL=F", "cp": "HG=F", "u10": "%5ETNX", "bt": "BTC-USD", 
        "vx": "%5EVIX", "v3": "%5EVIX3M", "u2": "2Y=F"
    }
    for key, sym in symbols.items():
        p, c = fy(sym)
        d[key+"p"] = p if p is not None else pre.get(key+"p")
        d[key+"c"] = c

    # 判定用変数の整理
    vix = d.get("vxp", 20.0)
    fgi = d.get("fgi", 50)
    u10 = d.get("u10p")
    u2 = d.get("u2p")
    sp = (u10 - u2) if (u10 and u2) else 0.0
    v3p = d.get("v3p")
    vr = vix / v3p if (v3p and v3p != 0) else 1.0

    # ニュースの仕分け
    vn, fn = [], []
    for url in FS:
        try:
            feed = fp.parse(url)
            for entry in feed.entries:
                full_text = (entry.title + entry.get("summary", "")).lower()
                if any(k in full_text for k in KW):
                    # 重要度判定
                    if any(k in full_text for k in ["ホルムズ","攻撃","ミサイル","封鎖","戦争"]):
                        im = "重大"
                    elif any(k in full_text for k in ["雇用統計","cpi","pce","fomc","利上げ","利下げ"]):
                        im = "強い影響"
                    elif any(k in full_text for k in ["関税","制裁","緊張","景気後退"]):
                        im = "中程度"
                    else:
                        im = "軽微"
                    
                    item = {"t": entry.title, "i": im}
                    # 信頼ドメインチェック
                    if any(dom in entry.link.lower() for dom in TR):
                        vn.append(item)
                    else:
                        fn.append(item)
        except:
            continue

    # スコアリング (155点満点)
    points = [
        25 if (d.get("nqc", 0) > 0) else 0,
        20 if (d.get("esc", 0) > 0) else 0,
        20 if (d.get("nkc", 0) > 0) else 0,
        25 if vix >= 30 else 15 if vix >= 25 else 5 if vix >= 20 else 0,
        20 if sp < 0 else 0,
        20 if (d.get("btc", 0) >= 3) else 0
    ]
    sc = sum(points)
    sl = min(max(int(sc / 155 * 100), 0), 100)

    # メッセージパーツの準備
    fgi_label = next(s for v, s in [(25,"極度の恐怖"),(45,"恐怖"),(55,"中立"),(75,"強欲"),(101,"極度の強欲")] if fgi <= v)
    mode_label = "🚨戦時モード：総合反転スコア" if vix >= 25 or fgi <= 20 else "🍀平時モード：トレンドスコア" if vix <= 18 and fgi >= 40 else "⚠️移行モード"
    yield_msg = "🚨逆イールド：景気後退の強い予兆。" if sp < 0 else "🔥急拡大：金利暴走による価格調整に注意。" if sp > 0.7 else "✅順イールド：金利体系は安定。"
    vix_status = "🚨異常(逆転)" if vr >= 1.0 else "⚠️警戒" if vr >= 0.9 else "✅正常"
    vix_sub = "パニック。反転間近。" if vr >= 1.0 else "緊張が高まっています。" if vr >= 0.9 else "市場は落ち着いています。"
    comm_msg = "🚨【スタ高警戒】" if (d.get("gdc",0)>0.5 and d.get("wtc",0)>1.0) else "📉【景気後退】銅安金高" if (d.get("gdc",0)>0.5 and d.get("cpc",0)<-1.0) else f"🏗️【銅の独歩高】{d.get('cpc',0):+.1f}%" if d.get("cpc',0)>1.5 else "⚖️【中立】レンジ内。"

    # ==========================================
    # 4. LINEメッセージ構築（ご指定のフォーマット）
    # ==========================================
    m = []
    m.append(f"【{d['date']} {mode_label}】\n")
    m.append(f"▼ 1. 投資家心理 (FGI)\n 【{fgi_label}】 指数: {fgi} （前日比：{fgi - d['fgp']:+d}pt）\n")
    m.append(f"▼ 2. 主要指数先物 & 相対強弱\n ・米 NQ100 : {f_val(d['nqp'])}（{d['nqc']:+.2f}%）\n ・米 S&P500: {f_val(d['esp'])}（{d['esc']:+.2f}%）\n ・日経平均 : {f_val(d['nkp'])}（{d['nkc']:+.2f}%）\n 💡 {('🇯🇵日本優位' if d['nkc']-(d['nqc']+d['esc'])/2>=0.5 else '🇺🇸米国優位' if d['nkc']-(d['nqc']+d['esc'])/2<=-0.5 else '⚖️日米拮抗')}\n")
    m.append(f"▼ 3. リスク指標 (VIX/VIX3M)\n ・VIX現物: {f_val(d['vxp'])}\n ・VIX比率: {vr:.2f} ({vix_status})\n 💡 {vix_sub}\n")
    m.append(f"▼ 4. 金利・イールド\n ・米10年債: {f_val(d['u10p'])}\n ・米 2年債: {f_val(d['u2p'])}\n ・利回り差: {sp:.3f}\n 💡 {yield_msg}\n")
    m.append(f"▼ 5. 商品 (Commodities)\n ・金 (Gold): {f_val(d['gdp'],'.1f')}（{d['gdc']:+.2f}%）\n ・原油(WTI): {f_val(d['wtp'])}（{d['wtc']:+.2f}%）\n ・銅 (Cop) : {f_val(d['cpp'],'.3f')}（{d['cpc']:+.2f}%）\n 💡 {comm_msg}\n")
    m.append(f"▼ 6. 仮想通貨 (Crypto)\n ・BTC: ${f_val(d['btp'],',.0f')}（{d['btc']:+.2f}%）\n 💡 {('🚀【リスクオン】' if d['btc']>3 else '💀【パニック】' if d['btc']<-3 else '⚖️【安定】リスク許容度は維持。')}\n")
    
    # ニュースセクション
    news_list = "\n".join([f"📰「{n['t'][:35]}」\n → 【{n['i']}】{('イベントです。' if n['i'] in ['重大','強い影響'] else 'ニュースです。')}" for n in vn[:5]])
    m.append(f"▼ 7. マクロニュース\n{news_list}")
    
    # Copilot分析
    ana = "地政学リスクや供給リスクに厳重な注意が必要です。" if "重大" in str(vn) else "決定的な転換要因は限定的ですが、注視が必要です。" if vn else "本日のマクロニュースは限定的です。"
    m.append(f"\n🤖 Copilot分析: {ana}")
    
    # 総合評価
    eval_txt = "全体的に警戒感が強く、キャッシュ保護を優先すべきです。" if vix>=25 or fgi<=25 else "リスクオンのムードが強く、押し目は拾われやすい環境です。" if fgi>=60 else "中立〜バランス型の地合いです。需給を見極める局面です。"
    m.append(f"\n▼ 8. 総合評価\n{eval_txt}\n")
    
    # 除外ニュース
    exclude_list = "\n".join([f"- {x['t']}" for x in fn[:3]])
    m.append(f"🚫 除外ニュース:\n{exclude_list}")
    
    # 最終スコアリング
    m.append(f"\n⚖️ 総合スコア：{sl}点 / 100 （素点: {sc} / 155）\n {'📈 打診買い検討' if sl >= 50 else '🌑 キャッシュ保護優先'}\n--------------------------")

    # 送信処理
    full_message = "\n".join(m)
    if L_TK and L_ID:
        requests.post("https://api.line.me/v2/bot/message/push", 
                      headers={"Authorization":f"Bearer {L_TK}","Content-Type":"application/json"}, 
                      data=json.dumps({"to":L_ID, "messages":[{"type":"text","text":full_message[:4800]}]}))
    else:
        print(full_message)
    
    # キャッシュ保存
    with open(CF, "wb") as f_out:
        pickle.dump(d, f_out)

if __name__ == "__main__":
    main()
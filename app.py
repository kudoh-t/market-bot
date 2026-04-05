import os
import json
import pickle
import requests
import feedparser as fp
from datetime import datetime as dt, timezone as tz, timedelta as td

# =================================================================
# 1. 環境設定・アイコン定義
# =================================================================
L_TK = os.getenv("LINE_ACCESS_TOKEN")
L_ID = os.getenv("LINE_USER_ID")
CF = "market_cache.pkl"

# エラーを回避するため絵文字は変数として定義。GitHub Actionsでも化けない形式。
# 16進数指定により unicodeescape エラーを物理的に排除
IC_ALRT = chr(0x1F6A8) # 🚨
IC_CLVR = chr(0x1F340) # 🍀
IC_WARN = chr(0x26A0)  # ⚠️
IC_BULB = chr(0x1F4A1) # 💡
IC_NEWS = chr(0x1F4F0) # 📰
IC_BOT  = chr(0x1F916) # 🤖
IC_SCAL = chr(0x2696)  # ⚖️
IC_ROCK = chr(0x1F680) # 🚀
IC_SKUL = chr(0x1F480) # 💀
IC_UP   = chr(0x1F4C8) # 📈
IC_MOON = chr(0x1F311) # 🌑
IC_NO   = chr(0x1F6AB) # 🚫
IC_FIRE = chr(0x1F525) # 🔥
IC_CHK  = chr(0x2705)  # ✅

# 信頼メディアとキーワード（62語を完全保持）
TR = ["reuters.com", "nhk.or.jp", "bloomberg.com", "apnews.com", "nikkei.com"]
FS = ["https://feeds.reuters.com/reuters/worldNews", "https://feeds.reuters.com/reuters/businessNews", "https://www.nhk.or.jp/rss/news/cat0.xml"]
KW = ["トランプ", "大統領", "関税", "イラン", "イスラエル", "ホルムズ", "攻撃", "ミサイル", "ウクライナ", "ロシア", "侵攻", "原油", "供給", "opec", "金利", "利上げ", "利下げ", "長期金利", "国債", "インフレ", "デフレ", "物価", "pce", "コアpce", "cpi", "ppi", "frb", "金融政策", "qt", "qe", "gdp", "pmi", "ism", "小売売上高", "住宅着工", "建設許可", "失業率", "雇用統計", "景気後退", "景気拡大", "リセッション", "決算", "ガイダンス", "予想上回る", "予想下回る", "eps", "利益率", "売上高", "業績", "中国", "不動産", "恒大", "碧桂園", "景気刺激策", "輸出", "減速", "不況", "財政赤字", "政府閉鎖", "インフラ投資", "減税", "規制強化", "テック規制"]

# =================================================================
# 2. 堅牢なデータ取得・書式化関数
# =================================================================
def get_price_data(sym):
    """Yahoo Financeから価格取得。失敗時はNoneを返し、TypeErrorを防ぐ"""
    try:
        r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}", headers={"User-Agent":"Mozilla/5.0"}, timeout=15).json()
        meta = r["chart"]["result"][0]["meta"]
        p = meta["regularMarketPrice"]
        c = (p - meta["chartPreviousClose"]) / meta["chartPreviousClose"] * 100
        return p, c
    except: return None, 0.0

def f_s(val, spec=".2f"):
    """画像5枚目の TypeError(NoneType) を解決する書式化関数"""
    if val is None: return "---"
    try: return format(float(val), spec)
    except: return "---"

# =================================================================
# 3. メインロジック
# =================================================================
def main():
    # キャッシュ読み込み
    pre = pickle.load(open(CF, "rb")) if os.path.exists(CF) else {}
    d = {"date": dt.now(tz(td(hours=9))).strftime("%Y.%m.%d")}
    
    # FGI取得
    try:
        rj = requests.get("https://api.alternative.me/fng/?limit=2", timeout=10).json()
        d["fgi"], d["fgp"] = int(rj["data"][0]["value"]), int(rj["data"][1]["value"])
    except: d["fgi"], d["fgp"] = pre.get("fgi", 50), pre.get("fgp", 50)
    
    # 市場データ取得
    syms = {"nq":"NQ=F", "es":"ES=F", "nk":"NK=F", "gd":"GC=F", "wt":"CL=F", "cp":"HG=F", "u10":"%5ETNX", "bt":"BTC-USD", "vx":"%5EVIX", "v3":"%5EVIX3M", "u2":"2Y=F"}
    for k, s in syms.items():
        p, c = get_price_data(s)
        d[k+"p"] = p if p is not None else pre.get(k+"p")
        d[k+"c"] = c

    # 判定用変数の計算（計算前にNoneチェック）
    vx, fgi = d.get("vxp", 20.0), d.get("fgi", 50)
    u10, u2 = d.get("u10p", 0), d.get("u2p", 0)
    sp = (u10 - u2) if (u10 and u2) else 0.0
    v3 = d.get("v3p", 20.0)
    vr = vx / v3 if (v3 and v3 != 0) else 1.0

    # ニュース仕分け
    vn, fn = [], []
    for u in FS:
        try:
            feed = fp.parse(u)
            for e in feed.entries:
                txt = (e.title + e.get("summary", "")).lower()
                if any(k in txt for k in KW):
                    if any(k in txt for k in ["ホルムズ","攻撃","ミサイル","封鎖","戦争"]): im = "重大"
                    elif any(k in txt for k in ["雇用統計","cpi","pce","fomc","利上げ","利下げ"]): im = "強い影響"
                    elif any(k in txt for k in ["関税","制裁","緊張","景気後退"]): im = "中程度"
                    else: im = "軽微"
                    item = {"t": e.title, "i": im}
                    (vn if any(dom in e.link.lower() for dom in TR) else fn).append(item)
        except: continue

    # スコア計算
    sc = sum([25 if d.get("nqc",0)>0 else 0, 20 if d.get("esc",0)>0 else 0, 20 if d.get("nkc",0)>0 else 0,
              25 if vx>=30 else 15 if vx>=25 else 5 if vx>=20 else 0, 20 if sp<0 else 0, 20 if d.get("btc",0)>=3 else 0])
    sl = min(max(int(sc / 155 * 100), 0), 100)

    # メッセージ組み立て（f-string内での辞書参照を避け、事前に変数化）
    fgi_l = next(s for v, s in [(25,"極度の恐怖"),(45,"恐怖"),(55,"中立"),(75,"強欲"),(101,"極度の強欲")] if fgi <= v)
    mode = f"{IC_ALRT}戦時モード" if vx>=25 or fgi<=20 else f"{IC_CLVR}平時モード" if vx<=18 and fgi>=40 else f"{IC_WARN}移行モード"
    y_msg = f"{IC_ALRT}逆イールド：景気後退の予兆。" if sp < 0 else f"{IC_FIRE}急拡大：価格調整に注意。" if sp > 0.7 else f"{IC_CHK}順イールド：安定。"
    v_msg = f"{IC_ALRT}異常(逆転)" if vr >= 1.0 else f"{IC_WARN}警戒" if vr >= 0.9 else f"{IC_CHK}正常"
    c_msg = f"{IC_ALRT}【スタ高警戒】" if (d.get("gdc",0)>0.5 and d.get("wtc",0)>1.0) else f"📉【景気後退】銅安金高" if (d.get("gdc",0)>0.5 and d.get("cpc",0)<-1.0) else f"🏗️【銅の独歩高】{d.get('cpc',0):+.1f}%" if d.get("cpc",0)>1.5 else f"{IC_SCAL}【中立】レンジ内。"
    btc_c = d.get("btc", 0.0)
    btc_tag = f"{IC_ROCK}【リスクオン】" if btc_c > 3 else f"{IC_SKUL}【パニック】" if btc_c < -3 else f"{IC_SCAL}【安定】リスク維持。"

    m = [
        f"【{d['date']} {mode}】\n",
        f"▼ 1. 投資家心理 (FGI)\n 【{fgi_l}】 指数: {fgi} （前日比：{fgi - d['fgp']:+d}pt）\n",
        f"▼ 2. 主要指数先物\n ・米 NQ100 : {f_s(d['nqp'])}（{d['nqc']:+.2f}%）\n ・米 S&P500: {f_s(d['esp'])}（{d['esc']:+.2f}%）\n ・日経平均 : {f_s(d['nkp'])}（{d['nkc']:+.2f}%）\n",
        f"▼ 3. リスク指標 (VIX/VIX3M)\n ・VIX現物: {f_s(d['vxp'])}\n ・VIX比率: {vr:.2f} ({v_msg})\n",
        f"▼ 4. 金利・イールド\n ・米10年債: {f_s(d['u10p'])}\n ・米 2年債: {f_s(d['u2p'])}\n ・利回り差: {sp:.3f}\n {IC_BULB} {y_msg}\n",
        f"▼ 5. 商品 (Commodities)\n ・金 (Gold): {f_s(d['gdp'],'.1f')}（{d['gdc']:+.2f}%）\n ・原油(WTI): {f_s(d['wtp'])}（{d['wtc']:+.2f}%）\n ・銅 (Cop) : {f_s(0 if d['cpp'] is None else d['cpp'],'.3f')}（{d['cpc']:+.2f}%）\n {IC_BULB} {c_msg}\n",
        f"▼ 6. 仮想通貨 (Crypto)\n ・BTC: ${f_s(d['btp'],',.0f')}（{btc_c:+.2f}%）\n {IC_BULB} {btc_tag}\n",
        f"▼ 7. マクロニュース\n" + "\n".join([f"{IC_NEWS}「{n['t'][:35]}」\n → 【{n['i']}】ニュースです。" for n in vn[:5]]),
        f"\n{IC_BOT} Copilot分析: {('厳重注意。' if '重大' in str(vn) else '注視が必要。' if vn else 'ニュース限定的。')}",
        f"\n▼ 8. 総合評価\n{('キャッシュ保護優先。' if vx>=25 or fgi<=25 else 'リスクオン。押し目買い。' if fgi>=60 else '中立地合い。')}\n",
        f"{IC_NO} 除外ニュース:\n" + "\n".join([f"- {x['t']}" for x in fn[:3]]),
        f"\n{IC_SCAL} 総合スコア：{sl}点 / 100\n {(IC_UP+' 打診買い検討' if sl >= 50 else IC_MOON+' キャッシュ保護優先')}\n--------------------------"
    ]

    full = "\n".join(m)
    if L_TK and L_ID:
        requests.post("https://api.line.me/v2/bot/message/push", headers={"Authorization":f"Bearer {L_TK}","Content-Type":"application/json"}, data=json.dumps({"to":L_ID,"messages":[{"type":"text","text":full[:4800]}]}))
    else: print(full)
    with open(CF, "wb") as fo: pickle.dump(d, fo)

if __name__ == "__main__": main()
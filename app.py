import os
import json
import pickle
import requests
import feedparser as fp
from datetime import datetime as dt, timezone as tz, timedelta as td

# =================================================================
# 1. 環境設定・定数定義
# =================================================================
# LINE通知用（GitHub ActionsのSettings > Secretsから取得）
L_TK = os.getenv("LINE_ACCESS_TOKEN")
L_ID = os.getenv("LINE_USER_ID")
# キャッシュファイル名（前日の値を保持し、騰落計算やFGI比較に使用）
CF = "market_cache.pkl"

# エラー回避用アイコン定義（GitHub Actionsでの絵文字化け・構文エラー防止）
IC_ALRT = "\U0001F6A8"  # 🚨 戦時・異常
IC_CLVR = "\U0001F340"  # 🍀 平時
IC_WARN = "\U000026A0"  # ⚠️ 警戒
IC_BULB = "\U0001F4A1"  # 💡 ヒント・補足
IC_NEWS = "\U0001F4F0"  # 📰 ニュース
IC_BOT  = "\U0001F916"  # 🤖 Copilot分析
IC_SCAL = "\U0002696"   # ⚖️ スコア・中立
IC_ROCK = "\U0001F680"  # 🚀 リスクオン
IC_SKUL = "\U0001F480"  # 💀 パニック
IC_UP   = "\U0001F4C8"  # 📈 打診買い
IC_MOON = "\U0001F311"  # 🌑 キャッシュ保護
IC_NO   = "\U0001F6AB"  # 🚫 除外
IC_FIRE = "\U0001F525"  # 🔥 金利急騰
IC_CHK  = "\U00002705"  # ✅ 正常

# ニュース取得元（信頼性の高いメインメディアを抽出）
TR = ["reuters.com", "nhk.or.jp", "bloomberg.com", "apnews.com", "nikkei.com"]
FS = [
    "https://feeds.reuters.com/reuters/worldNews",
    "https://feeds.reuters.com/reuters/businessNews",
    "https://www.nhk.or.jp/rss/news/cat0.xml"
]

# 監視キーワード（マクロ経済・地政学リスクを網羅する全62語）
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

# =================================================================
# 2. 補助関数定義
# =================================================================
def get_market_data(symbol):
    """Yahoo Finance APIから市場価格と前日比を取得（エラー時はNoneを返す）"""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=15).json()
        meta = r["chart"]["result"][0]["meta"]
        price = meta["regularMarketPrice"]
        prev_close = meta["chartPreviousClose"]
        change = (price - prev_close) / prev_close * 100
        return price, change
    except Exception:
        return None, 0.0

def safe_format(value, spec=".2f"):
    """データの欠損（None）が発生しても、書式指定エラーを回避して'---'を表示"""
    if value is None:
        return "---"
    return format(value, spec)

# =================================================================
# 3. メインアルゴリズム
# =================================================================
def main():
    # キャッシュ（前回実行時のデータ）の復元
    prev_data = pickle.load(open(CF, "rb")) if os.path.exists(CF) else {}
    # 日本時間（JST）の取得
    now_jst = dt.now(tz(td(hours=9)))
    current_market = {"date": now_jst.strftime("%Y.%m.%d")}
    
    # 投資家心理指数 (Fear & Greed Index) の取得
    try:
        fgi_req = requests.get("https://api.alternative.me/fng/?limit=2", timeout=10).json()
        current_market["fgi"] = int(fgi_req["data"][0]["value"])
        current_market["fgp"] = int(fgi_req["data"][1]["value"])
    except:
        current_market["fgi"] = prev_data.get("fgi", 50)
        current_market["fgp"] = prev_data.get("fgp", 50)
    
    # 各種市場シンボルの定義
    market_symbols = {
        "nq": "NQ=F", "es": "ES=F", "nk": "NK=F", "gd": "GC=F", 
        "wt": "CL=F", "cp": "HG=F", "u10": "%5ETNX", "bt": "BTC-USD", 
        "vx": "%5EVIX", "v3": "%5EVIX3M", "u2": "2Y=F"
    }
    
    # 市場データのループ取得
    for key, sym in market_symbols.items():
        price, change = get_market_data(sym)
        # 取得失敗時は前回のキャッシュ値を採用、騰落率は0固定
        current_market[key+"p"] = price if price is not None else prev_data.get(key+"p")
        current_market[key+"c"] = change

    # 指標の計算と判定用変数の整理
    vix_val = current_market.get("vxp", 20.0)
    fgi_val = current_market.get("fgi", 50)
    u10_val = current_market.get("u10p")
    u2_val  = current_market.get("u2p")
    # 利回り差（逆イールド判定用）
    spread = (u10_val - u2_val) if (u10_val and u2_val) else 0.0
    # VIX/VIX3M比率（パニック・ボトム判定用）
    v3_val = current_market.get("v3p", 20.0)
    vix_ratio = vix_val / v3_val if v3_val != 0 else 1.0

    # ニュースの抽出とフィルタリング
    valid_news, filtered_news = [], []
    for feed_url in FS:
        try:
            parsed = fp.parse(feed_url)
            for entry in parsed.entries:
                combined_text = (entry.title + entry.get("summary", "")).lower()
                if any(k in combined_text for k in KW):
                    # 重要キーワードに基づくラベル付け
                    if any(k in combined_text for k in ["ホルムズ","攻撃","ミサイル","封鎖","戦争"]):
                        importance = "重大"
                    elif any(k in combined_text for k in ["雇用統計","cpi","pce","fomc","利上げ","利下げ"]):
                        importance = "強い影響"
                    elif any(k in combined_text for k in ["関税","制裁","緊張","景気後退"]):
                        importance = "中程度"
                    else:
                        importance = "軽微"
                    
                    news_item = {"t": entry.title, "i": importance}
                    # 信頼ドメインに含まれるか否かで仕分け
                    if any(domain in entry.link.lower() for domain in TR):
                        valid_news.append(news_item)
                    else:
                        filtered_news.append(news_item)
        except:
            continue

    # 総合スコアリング計算 (155点満点ロジック)
    score_points = [
        25 if (current_market.get("nqc", 0) > 0) else 0, # ナスダックプラス
        20 if (current_market.get("esc", 0) > 0) else 0, # S&P500プラス
        20 if (current_market.get("nkc", 0) > 0) else 0, # 日経プラス
        25 if vix_val >= 30 else 15 if vix_val >= 25 else 5 if vix_val >= 20 else 0, # VIX高水準
        20 if spread < 0 else 0, # 逆イールド発生中
        20 if (current_market.get("btc", 0) >= 3) else 0 # クリプトリスクオン
    ]
    raw_score = sum(score_points)
    score_pct = min(max(int(raw_score / 155 * 100), 0), 100)

    # =================================================================
    # 4. メッセージ・ビルディング
    # =================================================================
    # 各種ステータスラベルの生成
    fgi_label = next(s for v, s in [(25,"極度の恐怖"),(45,"恐怖"),(55,"中立"),(75,"強欲"),(101,"極度の強欲")] if fgi_val <= v)
    mode_label = f"{IC_ALRT}戦時モード：総合反転スコア" if vix_val >= 25 or fgi_val <= 20 else f"{IC_CLVR}平時モード：トレンドスコア" if vix_val <= 18 and fgi_val >= 40 else f"{IC_WARN}移行モード"
    yield_msg = f"{IC_ALRT}逆イールド：景気後退の強い予兆。" if spread < 0 else f"{IC_FIRE}急拡大：価格調整に注意。" if spread > 0.7 else f"{IC_CHK}順イールド：金利体系は安定。"
    vix_status = f"{IC_ALRT}異常(逆転)" if vix_ratio >= 1.0 else f"{IC_WARN}警戒" if vix_ratio >= 0.9 else f"{IC_CHK}正常"
    vix_comment = "パニック。反転間近。" if vix_ratio >= 1.0 else "緊張が高まっています。" if vix_ratio >= 0.9 else "市場は落ち着いています。"
    comm_msg = f"{IC_ALRT}【スタ高警戒】" if (current_market.get("gdc",0)>0.5 and current_market.get("wtc",0)>1.0) else f"📉【景気後退】銅安金高" if (current_market.get("gdc",0)>0.5 and current_market.get("cpc",0)<-1.0) else f"🏗️【銅の独歩高】{current_market.get('cpc',0):+.1f}%" if current_market.get("cpc",0)>1.5 else f"{IC_SCAL}【中立】レンジ内。"

    # LINE送信用本文の構築
    msg = []
    msg.append(f"【{current_market['date']} {mode_label}】\n")
    
    msg.append(f"▼ 1. 投資家心理 (FGI)\n 【{fgi_label}】 指数: {fgi_val} （前日比：{fgi_val - current_market['fgp']:+d}pt）\n")
    
    relative_strength = '🇯🇵日本優位' if current_market['nkc']-(current_market['nqc']+current_market['esc'])/2>=0.5 else '🇺🇸米国優位' if current_market['nkc']-(current_market['nqc']+current_market['esc'])/2<=-0.5 else '⚖️日米拮抗'
    msg.append(f"▼ 2. 主要指数先物 & 相対強弱\n ・米 NQ100 : {safe_format(current_market['nqp'])}（{current_market['nqc']:+.2f}%）\n ・米 S&P500: {safe_format(current_market['esp'])}（{current_market['esc']:+.2f}%）\n ・日経平均 : {safe_format(current_market['nkp'])}（{current_market['nkc']:+.2f}%）\n {IC_BULB} {relative_strength}\n")
    
    msg.append(f"▼ 3. リスク指標 (VIX/VIX3M)\n ・VIX現物: {safe_format(current_market['vxp'])}\n ・VIX比率: {vix_ratio:.2f} ({vix_status})\n {IC_BULB} {vix_comment}\n")
    
    msg.append(f"▼ 4. 金利・イールド\n ・米10年債: {safe_format(current_market['u10p'])}\n ・米 2年債: {safe_format(current_market['u2p'])}\n ・利回り差: {spread:.3f}\n {IC_BULB} {yield_msg}\n")
    
    msg.append(f"▼ 5. 商品 (Commodities)\n ・金 (Gold): {safe_format(current_market['gdp'],'.1f')}（{current_market['gdc']:+.2f}%）\n ・原油(WTI): {safe_format(current_market['wtp'])}（{current_market['wtc']:+.2f}%）\n ・銅 (Cop) : {safe_format(current_market['cpp'],'.3f')}（{current_market['cpc']:+.2f}%）\n {IC_BULB} {comm_msg}\n")
    
    # 仮想通貨 (BTC) セクションの独立維持
    btc_p = safe_format(current_market.get('btp'), ',.0f')
    btc_c = current_market.get('btc', 0.0)
    btc_tag = f"{IC_ROCK}【リスクオン】" if btc_c > 3 else f"{IC_SKUL}【パニック】" if btc_c < -3 else f"{IC_SCAL}【安定】リスク許容度は維持。"
    msg.append(f"▼ 6. 仮想通貨 (Crypto)\n ・BTC: ${btc_p}（{btc_c:+.2f}%）\n {IC_BULB} {btc_tag}\n")
    
    news_list = "\n".join([f"{IC_NEWS}「{n['t'][:35]}」\n → 【{n['i']}】{('イベントです。' if n['i'] in ['重大','強い影響'] else 'ニュースです。')}" for n in valid_news[:5]])
    msg.append(f"▼ 7. マクロニュース\n{news_list}")
    
    # Copilot分析コメントの動的生成
    ana_comment = "地政学リスクや供給リスクに厳重な注意が必要です。" if "重大" in str(valid_news) else "決定的な転換要因は限定的ですが、注視が必要です。" if valid_news else "本日のマクロニュースは限定的です。"
    msg.append(f"\n{IC_BOT} Copilot分析: {ana_comment}")
    
    # 市場評価に基づく総合コメント
    eval_text = "全体的に警戒感が強く、キャッシュ保護を優先すべきです。" if vix_val>=25 or fgi_val<=25 else "リスクオンのムードが強く、押し目は拾われやすい環境です。" if fgi_val>=60 else "中立〜バランス型の地合いです。需給を見極める局面です。"
    msg.append(f"\n▼ 8. 総合評価\n{eval_text}\n")
    
    # 除外（非信頼ドメイン）ニュースの表示
    if filtered_news:
        ex_list = "\n".join([f"- {x['t']}" for x in filtered_news[:3]])
        msg.append(f"{IC_NO} 除外ニュース:\n{ex_list}\n")
    
    # 最終スコアとアクション指針
    msg.append(f"{IC_SCAL} 総合スコア：{score_pct}点 / 100 （素点: {raw_score} / 155）\n {(IC_UP+' 打診買い検討' if score_pct >= 50 else IC_MOON+' キャッシュ保護優先')}\n--------------------------")

    # メッセージの送信
    full_message = "\n".join(msg)
    if L_TK and L_ID:
        requests.post("https://api.line.me/v2/bot/message/push", 
                      headers={"Authorization":f"Bearer {L_TK}","Content-Type":"application/json"}, 
                      data=json.dumps({"to":L_ID, "messages":[{"type":"text","text":full_message[:4800]}]}))
    else:
        print(full_message)
    
    # 次回比較用にデータをキャッシュ保存
    with open(CF, "wb") as f_out:
        pickle.dump(current_market, f_out)

if __name__ == "__main__":
    main()
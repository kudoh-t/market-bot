import json
import os

# 既存の外部関数インポート
from analysis import (
    get_vix_analysis,
    get_yield_detail,
    get_commodities_analysis,
    get_equity_relative_comment,
    get_btc_comment,
)
from news_engine import (
    fetch_rss_news,
    classify_news_list,
    calculate_news_mode_score,
)

# ============================
# 前回データの保存・読み込み
# ============================
def load_prev_data():
    if not os.path.exists("prev.json"):
        return {}
    try:
        with open("prev.json", "r") as f:
            return json.load(f)
    except:
        return {}

def save_prev_data(data):
    try:
        # data 内のタプルなどを文字列等に変換して保存
        with open("prev.json", "w") as f:
            json.dump(data, f)
    except:
        pass

# ============================
# Copilot’s View
# ============================
def generate_copilot_view(mode, classified):
    if mode == "war":
        return (
            "地政学リスクが市場心理を圧迫しています。\n"
            "戦時ニュースが複数確認され、VIXも高止まり。\n"
            "反発局面は限定的となる可能性が高いです。"
        )
    elif mode == "peace":
        return (
            "市場はリスク許容度を取り戻しつつあります。\n"
            "平時ニュースが優勢で、金利・VIXも安定。\n"
            "押し目買いが機能しやすい環境です。"
        )
    else:
        return (
            "市場は方向感を探る展開です。\n"
            "地政学・金融政策ニュースが混在しており、\n"
            "短期的には上下に振れやすい相場が続きそうです。"
        )

# ============================
# 市場モード判定
# ============================
def determine_market_mode(vix_tuple, fgi, prev_vix, news_war, news_peace):
    # vix_tuple: (price, change)
    vix_p = vix_tuple[0] if vix_tuple else None
    
    if news_war > news_peace * 1.3:
        return "war", "🚨戦時モード：総合反転スコア"
    if news_peace > news_war * 1.3:
        return "peace", "🌤平時モード：安定回帰"
    return "neutral", "⚖️中立モード：方向感模索"

# ============================
# メッセージ構築
# ============================
def build_message(d):
    prev_data = load_prev_data()
    # 前回のVIX値を取得（前回保存分がタプルか単体数値か不明なため安全に取得）
    p_v = prev_data.get("vix", [0, 0])
    prev_vix = p_v[0] if isinstance(p_v, list) else 0

    # ① ニュース取得
    raw_news = fetch_rss_news(max_items=15)
    classified = classify_news_list(raw_news)
    news_war_score, news_peace_score = calculate_news_mode_score(classified)

    # ② 市場モード決定
    mode, mode_title = determine_market_mode(
        d.get("vix"), d.get("fgi"), prev_vix,
        news_war_score, news_peace_score
    )

    # ③ データ整形用関数（ここで f-string 内のエラーを回避）
    def fmt_val(data_tuple, dec=2, prefix=""):
        if not data_tuple or data_tuple[0] is None:
            return "取得失敗"
        price, change = data_tuple
        return f"{prefix}{price:.{dec}f}（{change:+.2f}%）"

    # ④ メッセージ配列作成
    msg = [
        f"【{d.get('date')} {mode_title}】\n",
        "▼ 1. 投資家心理 (FGI)",
        f" 【{d.get('fgi') if d.get('fgi') is not None else 'None'}】 （前日比：{d.get('fgi_prev') if d.get('fgi_prev') is not None else 'None'}）\n",

        "▼ 2. 主要指数先物 & 相対強弱",
        f" ・米 NQ100 : {fmt_val(d.get('nq'))}",
        f" ・米 S&P500: {fmt_val(d.get('spx'))}",
        f" ・日経平均 : {fmt_val(d.get('nky'))}",
        f" 💡 {get_equity_relative_comment(d.get('nky')[1], d.get('nq')[1], d.get('spx')[1]) if d.get('nky')[0] is not None else '相対強弱取得失敗'}\n",

        "▼ 3. リスク指標 (VIX)",
        f" ・VIX現物: {fmt_val(d.get('vix'))}",
        f" ・VIX先物: {fmt_val(d.get('vix_f'))}",
        f" 💡 {get_vix_analysis(d.get('vix')[0], d.get('vix_f')[0]) if d.get('vix')[0] is not None else 'VIX取得失敗'}\n",

        "▼ 4. 金利・イールド",
        f" ・米10年債: {fmt_val(d.get('us10y'))}",
        f" ・米 2年債: {fmt_val(d.get('us2y'))}",
    ]

    # 利回り差の表示部分（SyntaxErrorの原因箇所を安全に修正）
    spread = d.get("yield_spread")
    if spread is not None:
        msg.append(f" ・利回り差: {spread:.3f}")
    else:
        msg.append(" ・利回り差: 失敗")
    
    msg.append(f" 💡 {get_yield_detail(spread)}\n")

    # 残りのセクション
    msg.extend([
        "▼ 5. 商品 (Commodities)",
        f" ・金 (Gold): {fmt_val(d.get('gold'), 1)}",
        f" ・原油(WTI): {fmt_val(d.get('wti'))}",
        f" ・銅 (Cop) : {fmt_val(d.get('copper'), 3)}",
        f" 💡 {get_commodities_analysis(d.get('gold')[1], d.get('wti')[1], d.get('copper')[1]) if d.get('gold')[0] is not None else 'コモディティ取得失敗'}\n",

        "▼ 6. 仮想通貨 (Crypto)",
        f" ・BTC: {fmt_val(d.get('btc'), 0, '$')}",
        f" 💡 {get_btc_comment(d.get('btc')[1]) if d.get('btc')[0] is not None else 'BTC取得失敗'}\n",

        "--------------------------",
        "▼ 7. 主要ニュース（カテゴリ別）",
    ])

    # ニュース
    cat_map = {"geopolitics":"【地政学】","monetary":"【金融政策】","commodity":"【コモディティ】","equity":"【株式】","other":"【その他】"}
    for cat in ["geopolitics", "monetary", "commodity", "equity", "other"]:
        items = classified["categories"].get(cat, [])
        if items:
            msg.append(cat_map.get(cat, "【その他】"))
            for item in items[:3]:
                msg.append(f"・{item['title']}（{item['source']}）")

    msg.append("--------------------------")
    msg.append("--- 🤖 Copilot's View ---")
    msg.append(generate_copilot_view(mode, classified))

    save_prev_data(d)
    return "\n".join(msg)
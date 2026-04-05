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
import json
import os

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
        with open("prev.json", "w") as f:
            json.dump(data, f)
    except:
        pass

# ============================
# Copilot’s View（3段階）
# ============================

def generate_copilot_view(mode, classified):
    """
    mode: "war", "peace", "neutral"
    """

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
# 市場モード判定（ニュース統合）
# ============================

def determine_market_mode(vix_p, fgi, prev_vix, news_war, news_peace):
    """
    戦時/平時ニューススコアを統合して市場モードを決定
    """

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
    prev_vix = prev_data.get("vix_p") or 0

    # ----------------------------
    # ① RSSニュース取得
    # ----------------------------
    raw_news = fetch_rss_news(max_items=15)

    # ----------------------------
    # ② ニュース分類
    # ----------------------------
    classified = classify_news_list(raw_news)

    # ----------------------------
    # ③ ニューススコア（信頼度反映）
    # ----------------------------
    news_war_score, news_peace_score = calculate_news_mode_score(classified)

    # ----------------------------
    # ④ 市場モード判定
    # ----------------------------
    mode, mode_title = determine_market_mode(
        d.get("vix_p"), d.get("fgi_score"), prev_vix,
        news_war_score, news_peace_score
    )

    # ----------------------------
    # ⑤ 市場データの整形
    # ----------------------------

    def fmt(p, c, dec=2):
        return f"{p:.{dec}f}（{c:+.2f}%）" if p is not None else "取得失敗"

    # ----------------------------
    # ⑥ メッセージ本文
    # ----------------------------

    msg = [
        f"【{d.get('date')} {mode_title}】\n",

        "▼ 1. 投資家心理 (FGI)",
        f" 【{d.get('fgi_score')}】 （前日比：{d.get('fgi_prev')}）\n",

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
        (
            f" ・利回り差: {d.get('spread'):.3f}"
            if d.get("spread") is not None
            else " ・利回り差: 失敗"
        ),
        f" 💡 {get_yield_detail(d.get('spread'))}\n",

        "▼ 5. 商品 (Commodities)",
        f" ・金 (Gold): {fmt(d.get('gold_p'), d.get('gold_c'), 1)}",
        f" ・原油(WTI): {fmt(d.get('wti_p'), d.get('wti_c'))}",
        f" ・銅 (Cop) : {fmt(d.get('cop_p'), d.get('cop_c'), 3)}",
        f" 💡 {get_commodities_analysis(d.get('gold_c'), d.get('wti_c'), d.get('cop_c'))}\n",

        "▼ 6. 仮想通貨 (Crypto)",
        f" ・BTC: ${fmt(d.get('btc_p'), d.get('btc_c'), 0)}",
        f" 💡 {get_btc_comment(d.get('btc_c'))}\n",

        "--------------------------",
        "▼ 7. 主要ニュース（カテゴリ別）",
    ]

    # ----------------------------
    # ⑦ ニュースカテゴリ別表示
    # ----------------------------

    for cat, items in classified["categories"].items():
        if len(items) == 0:
            continue

        cat_name = {
            "geopolitics": "【地政学】",
            "monetary": "【金融政策】",
            "commodity": "【コモディティ】",
            "equity": "【株式】",
            "other": "【その他】",
        }.get(cat, "【その他】")

        msg.append(cat_name)
        for item in items[:3]:
            msg.append(f"・{item['title']}（{item['source']}）")

    msg.append("--------------------------")

    # ----------------------------
    # ⑧ Copilot’s View（3段階）
    # ----------------------------

    view = generate_copilot_view(mode, classified)
    msg.append("--- 🤖 Copilot's View ---")
    msg.append(view)

    # 保存
    save_prev_data(d)

    return "\n".join(msg)


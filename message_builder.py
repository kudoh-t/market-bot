import json
import os

# --- 外部モジュール ---
from news_engine import (
    fetch_rss_news,
    classify_news_list,
    calculate_news_mode_score,
    NEWS_SOURCE_SCORE
)

from analysis import analyze_market


# ============================
# ヘルパー関数：安全なフォーマット
# ============================
def safe_fmt(val_tuple, dec=2, prefix=""):
    if not val_tuple or not isinstance(val_tuple, (tuple, list)) or val_tuple[0] is None:
        return "取得失敗"
    return f"{prefix}{val_tuple[0]:.{dec}f}（{val_tuple[1]:+.2f}%）"


# ============================
# Copilot's View
# ============================
def generate_copilot_view(mode):
    views = {
        "war": "地政学リスクが市場を圧迫中。反発局面は限定的と予想されます。",
        "peace": "リスク許容度が回復。押し目買いが機能しやすい環境です。",
        "neutral": "方向感模索。地政学と金融政策が混在し、上下に振れやすい展開です。"
    }
    return views.get(mode, views["neutral"])


# ============================
# メッセージ構築（完全統合版）
# ============================
def build_message(d):

    # --------------------------
    # ① ニュース解析
    # --------------------------
    raw_news = fetch_rss_news(max_items=15)
    classified = classify_news_list(raw_news)
    n_war, n_peace = calculate_news_mode_score(classified)

    # --------------------------
    # ② モード判定
    # --------------------------
    if n_war > n_peace * 1.3:
        mode, title = "war", "🚨戦時モード：総合反転スコア"
    elif n_peace > n_war * 1.3:
        mode, title = "peace", "🌤平時モード：安定回帰"
    else:
        mode, title = "neutral", "⚖️中立モード：方向感模索"

    # --------------------------
    # ③ 市場分析コメント生成（analysis.py）
    # --------------------------
    market_analysis = analyze_market(
        market={
            "fgi": d.get("fgi"),
            "nasdaq_change": d.get("nq")[1],
            "sp500_change": d.get("spx")[1],
            "nikkei_change": d.get("nky")[1],
            "vix_change": d.get("vix")[1],
            "vix_futures_change": d.get("vix_f")[1],
            "us10y_change": d.get("us10y")[1],
            "us2y_change": d.get("us2y")[1],
            "yield_spread": d.get("yield_spread"),
            "gold_change": d.get("gold")[1],
            "wti_change": d.get("wti")[1],
            "copper_change": d.get("copper")[1] if d.get("copper") else 0,
            "btc_change": d.get("btc")[1],
        },
        classified_news=classified,
        war_score=n_war,
        peace_score=n_peace
    )

    # --------------------------
    # ④ メッセージ本文
    # --------------------------
    spread = d.get('yield_spread')
    spread_str = f"{spread:.3f}" if spread is not None else "失敗"

    msg = [
        f"【{d.get('date')} {title}】\n",

        # --- 1. FGI ---
        f"▼ 1. 投資家心理 (FGI)\n 【{d.get('fgi')}】（前日比：{d.get('fgi_prev')}）\n",

        # --- 2. 指数 ---
        "▼ 2. 主要指数先物",
        f" ・米 NQ100 : {safe_fmt(d.get('nq'))}",
        f" ・米 S&P500: {safe_fmt(d.get('spx'))}",
        f" ・日経平均 : {safe_fmt(d.get('nky'))}\n",

        # --- 3. VIX ---
        "▼ 3. リスク指標 (VIX)",
        f" ・VIX現物: {safe_fmt(d.get('vix'))}",
        f" ・VIX先物: {safe_fmt(d.get('vix_f'))}\n",

        # --- 4. 金利 ---
        "▼ 4. 金利",
        f" ・米10年債: {safe_fmt(d.get('us10y'))}",
        f" ・米2年債 : {safe_fmt(d.get('us2y'))}",
        f" ・利回り差: {spread_str}\n",

        # --- 5. コモディティ ---
        "▼ 5. 商品",
        f" ・原油(WTI): {safe_fmt(d.get('wti'))}",
        f" ・金 (Gold): {safe_fmt(d.get('gold'), 1)}",
        f" ・銅 (Copper): {safe_fmt(d.get('copper'))}\n",

        # --- 6. 仮想通貨 ---
        "▼ 6. 仮想通貨",
        f" ・BTC: {safe_fmt(d.get('btc'), 0, '$')}\n",

        "--------------------------",
        "▼ 7. 主要ニュース"
    ]

    # --------------------------
    # ⑤ ニュース表示（出所＋個別スコア）
    # --------------------------
    for cat, label in {
        "geopolitics": "【地政学】",
        "monetary": "【金融政策】",
        "other": "【その他】"
    }.items():

        items = classified["categories"].get(cat, [])
        if items:
            msg.append(label)
            for it in items[:2]:
                src = it.get('source', '不明')
                indiv_score = NEWS_SOURCE_SCORE.get(src, 50)
                msg.append(f"・{it['title']} ({src}:{indiv_score})")

    msg.append(f"\n[ニュース判定スコア] 戦時:{n_war} / 平時:{n_peace}")

    # --------------------------
    # ⑥ 市場コメント（analysis.py）
    # --------------------------
    msg.append("\n--------------------------")
    msg.append("▼ 8. 市場コメント")
    msg.append(f"・VIX: {market_analysis['vix_comment']}")
    msg.append(f"・金利: {market_analysis['rate_total_comment']}")
    msg.append(f"・コモディティ: {market_analysis['commodity_comment']}")
    msg.append(f"・株式相対強弱: {market_analysis['equity_comment']}")
    msg.append(f"・BTC: {market_analysis['btc_comment']}")

    # --------------------------
    # ⑦ 総合反転スコア（100点版）
    # --------------------------
    msg.append("\n--------------------------")
    msg.append("▼ 9. 総合反転スコア")
    msg.append(f" {market_analysis['reversal_score']} / 100\n")

    # --------------------------
    # ⑧ Copilot's View
    # --------------------------
    msg.append("--- 🤖 Copilot's View ---")
    msg.append(generate_copilot_view(mode))

    return "\n".join(msg)

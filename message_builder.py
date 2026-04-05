import json
import os
from news_engine import fetch_rss_news, classify_news_list, calculate_news_mode_score

# ヘルパー関数：安全なフォーマット
def safe_fmt(val_tuple, dec=2, prefix=""):
    if not val_tuple or not isinstance(val_tuple, (tuple, list)) or val_tuple[0] is None:
        return "取得失敗"
    return f"{prefix}{val_tuple[0]:.{dec}f}（{val_tuple[1]:+.2f}%）"

def generate_copilot_view(mode):
    views = {
        "war": "地政学リスクが市場を圧迫中。反発局面は限定的と予想されます。",
        "peace": "リスク許容度が回復。押し目買いが機能しやすい環境です。",
        "neutral": "方向感模索。地政学と金融政策が混在し、上下に振れやすい展開です。"
    }
    return views.get(mode, views["neutral"])

def build_message(d):
    # ニュース解析
    raw_news = fetch_rss_news(max_items=15)
    classified = classify_news_list(raw_news)
    n_war, n_peace = calculate_news_mode_score(classified)

    # モード判定
    if n_war > n_peace * 1.3: mode, title = "war", "🚨戦時モード：総合反転スコア"
    elif n_peace > n_war * 1.3: mode, title = "peace", "🌤平時モード：安定回帰"
    else: mode, title = "neutral", "⚖️中立モード：方向感模索"

    # 利回り差の文字列作成
    spread = d.get('yield_spread')
    spread_str = f"{spread:.3f}" if spread is not None else "失敗"

    msg = [
        f"【{d.get('date')} {title}】\n",
        f"▼ 1. 投資家心理 (FGI)\n 【{d.get('fgi')}】（前日比：{d.get('fgi_prev')}）\n",
        f"▼ 2. 主要指数先物\n ・米 NQ100 : {safe_fmt(d.get('nq'))}\n ・米 S&P500: {safe_fmt(d.get('spx'))}\n ・日経平均 : {safe_fmt(d.get('nky'))}\n",
        f"▼ 3. リスク指標 (VIX)\n ・VIX現物: {safe_fmt(d.get('vix'))}\n ・VIX先物: {safe_fmt(d.get('vix_f'))}\n",
        f"▼ 4. 金利\n ・米10年債: {safe_fmt(d.get('us10y'))}\n ・利回り差: {spread_str}\n",
        f"▼ 5. 商品\n ・原油(WTI): {safe_fmt(d.get('wti'))}\n ・金 (Gold): {safe_fmt(d.get('gold'), 1)}\n",
        f"▼ 6. 仮想通貨\n ・BTC: {safe_fmt(d.get('btc'), 0, '$')}\n",
        "--------------------------\n▼ 7. 主要ニュース"
    ]

    for cat, label in {"geopolitics":"【地政学】","monetary":"【金融政策】","other":"【その他】"}.items():
        items = classified["categories"].get(cat, [])
        if items:
            msg.append(label)
            for it in items[:2]: msg.append(f"・{it['title']}")

    msg.append("--------------------------\n--- 🤖 Copilot's View ---")
    msg.append(generate_copilot_view(mode))
    
    return "\n".join(msg)
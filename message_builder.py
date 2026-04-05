import json
import os
from analysis import *
from news_engine import fetch_rss_news, classify_news_list, calculate_news_mode_score

def load_prev_data():
    if not os.path.exists("prev.json"): return {}
    try:
        with open("prev.json", "r") as f: return json.load(f)
    except: return {}

def save_prev_data(data):
    try:
        with open("prev.json", "w") as f: json.dump(data, f)
    except: pass

def generate_copilot_view(mode, classified):
    if mode == "war":
        return "地政学リスクが市場心理を圧迫しています。戦時ニュースが複数確認され、反発局面は限定的となる可能性が高いです。"
    elif mode == "peace":
        return "市場はリスク許容度を取り戻しつつあります。平時ニュースが優勢で、押し目買いが機能しやすい環境です。"
    return "市場は方向感を探る展開です。地政学・金融政策ニュースが混在しており、短期的には上下に振れやすいです。"

def build_message(d):
    # ニュース解析とモード判定
    raw_news = fetch_rss_news(max_items=15)
    classified = classify_news_list(raw_news)
    n_war, n_peace = calculate_news_mode_score(classified)

    if n_war > n_peace * 1.3: mode, title = "war", "🚨戦時モード：総合反転スコア"
    elif n_peace > n_war * 1.3: mode, title = "peace", "🌤平時モード：安定回帰"
    else: mode, title = "neutral", "⚖️中立モード：方向感模索"

    def fmt(val_tuple, dec=2, pre=""):
        if not val_tuple or not isinstance(val_tuple, (list, tuple)) or val_tuple[0] is None: 
            return "取得失敗"
        return f"{pre}{val_tuple[0]:.{dec}f}（{val_tuple[1]:+.2f}%）"

    msg = [
        f"【{d.get('date')} {title}】\n",
        f"▼ 1. 投資家心理 (FGI)\n 【{d.get('fgi')}】（前日比：{d.get('fgi_prev')}）\n",
        f"▼ 2. 主要指数先物\n ・米 NQ100 : {fmt(d.get('nq'))}\n ・米 S&P500: {fmt(d.get('spx'))}\n ・日経平均 : {fmt(d.get('nky'))}\n",
        f"▼ 3. リスク指標 (VIX)\n ・VIX現物: {fmt(d.get('vix'))}\n ・VIX先物: {fmt(d.get('vix_f'))}\n",
        f"▼ 4. 金利\n ・米10年債: {fmt(d.get('us10y'))}\n ・利回り差: {f'{d.get('yield_spread'):.3f}' if d.get('yield_spread') else '失敗'}\n",
        f"▼ 5. 商品\n ・原油(WTI): {fmt(d.get('wti'))}\n ・金 (Gold): {fmt(d.get('gold'), 1)}\n",
        f"▼ 6. 仮想通貨\n ・BTC: {fmt(d.get('btc'), 0, '$')}\n",
        "--------------------------\n▼ 7. 主要ニュース"
    ]

    # ニュースの抽出
    for cat, label in {"geopolitics":"【地政学】","monetary":"【金融政策】","other":"【その他】"}.items():
        items = classified["categories"].get(cat, [])
        if items:
            msg.append(label)
            for it in items[:2]: msg.append(f"・{it['title']}")

    msg.append("--------------------------\n--- 🤖 Copilot's View ---")
    msg.append(generate_copilot_view(mode, classified))
    
    save_prev_data(d)
    return "\n".join(msg)
import json
import os

# 既存の外部関数インポート（ここはそのままでOK）
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
        with open("prev.json", "w") as f:
            json.dump(data, f)
    except:
        pass

# ============================
# 市場モード判定（安定化版）
# ============================
def determine_market_mode(vix_tuple, fgi, prev_vix, news_war, news_peace):
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

    # ③ データ整形用ヘルパー（重要：Noneを安全に処理）
    def fmt_val(data_tuple, dec=2, prefix=""):
        if not isinstance(data_tuple, (tuple, list)) or data_tuple[0] is None:
            return "取得失敗"
        price, change = data_tuple
        return f"{prefix}{price:.{dec}f}（{change:+.2f}%）"

    def get_val(data_tuple, idx):
        """タプルから安全に値を取り出す"""
        if isinstance(data_tuple, (tuple, list)) and len(data_tuple) > idx:
            return data_tuple[idx]
        return None

    # ④ メッセージ作成
    msg = []
    msg.append(f"【{d.get('date')} {mode_title}】\n")
    
    msg.append("▼ 1. 投資家心理 (FGI)")
    msg.append(f" 【{d.get('fgi') if d.get('fgi') is not None else 'None'}】 （前日比：{d.get('fgi_prev') if d.get('fgi_prev') is not None else 'None'}）\n")

    msg.append("▼ 2. 主要指数先物 & 相対強弱")
    msg.append(f" ・米 NQ100 : {fmt_val(d.get('nq'))}")
    msg.append(f" ・米 S&P500: {fmt_val(d.get('spx'))}")
    msg.append(f" ・日経平均 : {fmt_val(d.get('nky'))}")
    
    # 指数コメント
    nk_c = get_val(d.get('nky'), 1)
    nq_c = get_val(d.get('nq'), 1)
    spx_c = get_val(d.get('spx'), 1)
    msg.append(f" 💡 {get_equity_relative_comment(nk_c, nq_c, spx_c) if nk_c is not None else '相対強弱取得失敗'}\n")

    msg.append("▼ 3. リスク指標 (VIX)")
    msg.append(f" ・VIX現物: {fmt_val(d.get('vix'))}")
    msg.append(f" ・VIX先物: {fmt_val(d.get('vix_f'))}") # market_data.pyのキー名に合わせる
    
    vix_p = get_val(d.get('vix'), 0)
    vxf_p = get_val(d.get('vix_f'), 0)
    msg.append(f" 💡 {get_vix_analysis(vix_p, vxf_p) if vix_p is not None else 'VIX分析不可'}\n")

    msg.append("▼ 4. 金利・イールド")
    msg.append(f" ・米10年債: {fmt_val(d.get('us10y'))}")
    msg.append(f" ・米 2年債: {fmt_val(d.get('us2y'))}")
    spread = d.get("yield_spread")
    msg.append(f" ・利回り差: {f'{spread:.3f}' if spread is not None else '失敗'}")
    msg.append(f" 💡 {get_yield_detail(spread)}\n")

    msg.append("▼ 5. 商品 (Commodities)")
    msg.append(f" ・金 (Gold): {fmt_val(d.get('gold'), 1)}")
    msg.append(f" ・原油(WTI): {fmt_val(d.get('wti'))}")
    msg.append(f" ・銅 (Cop) : {fmt_val(d.get('copper'), 3)}")
    
    gold_c = get_val(d.get('gold'), 1)
    wti_c = get_val(d.get('wti'), 1)
    cop_c = get_val(d.get('copper'), 1)
    msg.append(f" 💡 {get_commodities_analysis(gold_c, wti_c, cop_c) if gold_c is not None else 'コモディティ分析不可'}\n")

    msg.append("▼ 6. 仮想通貨 (Crypto)")
    btc_tuple = d.get('btc')
    msg.append(f" ・BTC: {fmt_val(btc_tuple, 0, '$')}")
    btc_c = get_val(btc_tuple, 1)
    msg.append(f" 💡 {get_btc_comment(btc_c) if btc_c is not None else 'BTC取得失敗'}\n")

    msg.append("--------------------------")
    msg.append("▼ 7. 主要ニュース（カテゴリ別）")

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
    
    # View生成用のダミー
    from message_builder import generate_copilot_view
    msg.append(generate_copilot_view(mode, classified))

    save_prev_data(d)
    return "\n".join(msg)
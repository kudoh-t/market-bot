# ============================
#  message_builder.py（完全版）
# ============================

# --- 数値フォーマッタ（有効数字最適化） ---
def safe_fmt(value):
    if value is None:
        return "N/A"

    if isinstance(value, tuple) and len(value) == 2:
        v, diff = value
        return f"{fmt_number(v)} ({fmt_change(diff)})"

    return fmt_number(value)


def fmt_number(v):
    if v is None:
        return "N/A"

    if 50 < v < 200:
        return f"{v:.3f}"

    if v > 1000:
        return f"{v:.1f}"

    if v < 1000:
        return f"{v:.2f}"

    return f"{v:.2f}"


def fmt_change(diff):
    if diff is None:
        return "N/A"
    sign = "+" if diff >= 0 else ""
    return f"{sign}{diff:.2f}%"


# ============================
# タイトル生成（戦時/平時/移行期）
# ============================
def generate_title(data):
    date = data.get("date", "0000.00.00")

    vix = data.get("vix")
    vix_price = vix[0] if vix else None

    if vix_price is None:
        mode = "モード不明"
        icon = "ℹ️"
    elif vix_price > 25:
        mode = "戦時モード"
        icon = "🚨"
    elif vix_price < 18:
        mode = "平時モード"
        icon = "🌤️"
    else:
        mode = "移行期"
        icon = "⚠️"

    return f"【{date} {icon}{mode}：総合反転スコア】"


# ============================
# メインメッセージ生成
# ============================
def build_message(d):

    title = generate_title(d)

    # --- 0. FGI ---
    section_fgi = [
        title,
        "",
        "▼ 0. 投資家心理 (FGI)",
        f" ・FGI: {safe_fmt(d.get('fgi'))}",
        f" ・前日比: {safe_fmt(d.get('fgi_prev'))}\n",
    ]

    # --- 1. 日本市場 ---
    section_japan = [
        "▼ 1. 日本市場",
        f" ・日経平均: {safe_fmt(d.get('nikkei'))}",
        f" ・TOPIX: {safe_fmt(d.get('topix'))}",
        f" ・マザーズ: {safe_fmt(d.get('mothers'))}\n",
    ]

    # --- 2. 米国市場 ---
    section_us = [
        "▼ 2. 米国市場",
        f" ・NYダウ: {safe_fmt(d.get('dow'))}",
        f" ・S&P500: {safe_fmt(d.get('sp500'))}",
        f" ・NASDAQ: {safe_fmt(d.get('nasdaq'))}\n",
    ]

    # --- 3. VIX ---
    section_vix = [
        "▼ 3. リスク指標 (VIX)",
        f" ・VIX現物: {safe_fmt(d.get('vix'))}",
        f" ・VIX先物{'※推定値' if d.get('vix_f_est') else ''}: {safe_fmt(d.get('vix_f'))}\n",
    ]

    # --- 4. 為替 ---
    section_fx = [
        "▼ 4. 為替",
        f" ・USD/JPY: {safe_fmt(d.get('usd_jpy'))}",
        f" ・EUR/JPY: {safe_fmt(d.get('eur_jpy'))}",
        f" ・CNY/JPY: {safe_fmt(d.get('cny_jpy'))}\n",
    ]

    # --- 5. 商品 ---
    section_commodities = [
        "▼ 5. 商品",
        f" ・原油(WTI): {safe_fmt(d.get('wti'))}",
        f" ・金 (Gold): {safe_fmt(d.get('gold'))}",
        f" ・銀 (Silver): {safe_fmt(d.get('silver'))}",
        f" ・銅 (Copper): {safe_fmt(d.get('copper'))}",
        f" ・天然ガス: {safe_fmt(d.get('natgas'))}\n",
    ]

    # --- 6. 仮想通貨 ---
    section_crypto = [
        "▼ 6. 仮想通貨",
        f" ・BTC: {safe_fmt(d.get('btc'))}",
        f" ・ETH: {safe_fmt(d.get('eth'))}\n",
    ]

    # --- 7. コメント ---
    section_comment = [
        "▼ 7. コメント",
        d.get("comment", "N/A"),
        "\n",
    ]

    # --- 8. Copilot View ---
    section_copilot = [
        "▼ 8. Copilot View",
        d.get("copilot_view", "N/A"),
        "\n",
    ]

    # --- 9. 総合スコア ---
    section_score = [
    "▼ 9. 総合スコア",
    f" ・スコア: {d.get('score', 'N/A')} / 100",
    f" ・素点: {d.get('raw_score', 'N/A')} / {d.get('raw_max', 'N/A')}",
    f" ・判定: {d.get('judge', 'N/A')}",
    ]


    message = "\n".join(
        section_fgi
        + section_japan
        + section_us
        + section_vix
        + section_fx
        + section_commodities
        + section_crypto
        + section_comment
        + section_copilot
        + section_score
    )

    return message

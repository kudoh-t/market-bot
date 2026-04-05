# ============================
#  message_builder.py（完全版）
# ============================

# --- 数値フォーマッタ（有効数字最適化） ---
def safe_fmt(value):
    """
    (value, change) タプルにも対応しつつ、有効数字を自動調整するフォーマッタ
    """
    if value is None:
        return "N/A"

    # --- タプル形式 (value, change%) ---
    if isinstance(value, tuple) and len(value) == 2:
        v, diff = value
        return f"{fmt_number(v)} ({fmt_change(diff)})"

    # --- 単体の値 ---
    return fmt_number(value)


def fmt_number(v):
    """値に応じて自動で桁数を調整する"""

    if v is None:
        return "N/A"

    # FX → 小数点3桁
    if 50 < v < 200:
        return f"{v:.3f}"

    # BTC / ETH → 小数点1〜2桁
    if v > 1000:
        return f"{v:.1f}"

    # コモディティ → 小数点2桁
    if v < 1000:
        return f"{v:.2f}"

    # デフォルト
    return f"{v:.2f}"


def fmt_change(diff):
    """変化率は小数点2桁に統一"""
    if diff is None:
        return "N/A"
    sign = "+" if diff >= 0 else ""
    return f"{sign}{diff:.2f}%"


# ============================
#  メインメッセージ生成
# ============================

def build_message(d):
    """
    d: dict 形式のマーケットデータ
    """

    # --- 0. FGI ---
    section_fgi = [
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

    # --- 7. コメント（AIコメント） ---
    section_comment = [
        "▼ 7. コメント",
        d.get("comment", "N/A"),
        "\n",
    ]

    # --- 8. Copilot View（あなたのAIコメント） ---
    section_copilot = [
        "▼ 8. Copilot View",
        d.get("copilot_view", "N/A"),
        "\n",
    ]

    # --- 9. 総合スコア ---
    section_score = [
        "▼ 9. 総合スコア",
        f" ・スコア: {d.get('score', 'N/A')}",
        f" ・素点: {d.get('raw_score', 'N/A')}",
        f" ・判定: {d.get('judge', 'N/A')}",
    ]

    # --- 全体を結合 ---
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

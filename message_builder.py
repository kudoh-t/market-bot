# ============================
#  message_builder.py（完成版）
# ============================

# --- safe formatter ---
def safe_fmt(value):
    if value is None:
        return "N/A"
    return value


def build_message(d):
    """
    d: dict 形式のマーケットデータ
    """

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
        safe_fmt(d.get("comment")),
    ]

    # --- 全体を結合 ---
    message = "\n".join(
        section_japan
        + section_us
        + section_vix
        + section_fx
        + section_commodities
        + section_crypto
        + section_comment
    )

    return message

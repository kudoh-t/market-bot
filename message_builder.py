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
def build_news_section(data):
    classified = data.get("classified_news", {})
    # 前回の修正で追加した sort_news_by_category を適用
    classified = sort_news_by_category(classified)
    categories = classified.get("categories", {})

    # カテゴリの取得（新設の industry を追加）
    geopolitics = categories.get("geopolitics", [])
    monetary = categories.get("monetary", [])
    industry = categories.get("industry", []) # ★ 追加
    other = categories.get("other", [])

    lines = []

    # 1. 産業・テックニュース（実体経済のポジティブ要因を優先表示）
    if industry:
        lines.append("【産業・テック】")
        for n in industry[:3]:
            lines.append(f"・{n['title']} ({n['source']} {n['normalized_score']}点)")
        lines.append("")

    # 2. 金融政策ニュース
    if monetary:
        lines.append("【金融政策】")
        for n in monetary[:3]:
            lines.append(f"・{n['title']} ({n['source']} {n['normalized_score']}点)")
        lines.append("")

    # 3. 地政学ニュース
    if geopolitics:
        lines.append("【地政学リスク】")
        for n in geopolitics[:3]:
            lines.append(f"・{n['title']} ({n['source']} {n['normalized_score']}点)")
        lines.append("")

    return "\n".join(lines).strip()

def sort_news_by_category(classified):
    for cat in ["geopolitics", "monetary", "other"]:
        classified["categories"][cat].sort(
            key=lambda x: x["normalized_score"],
            reverse=True
        )
    return classified


def build_message(d):
    title = generate_title(d)

    section_fgi = [
        title,
        "",
        "▼ 0. 投資家心理 (FGI)",
        f" ・FGI: {safe_fmt(d.get('fgi'))}",
        f" ・前日比: {safe_fmt(d.get('fgi_prev'))}\n",
        f" ・コメント: {d.get('fgi_comment')}\n",
    ]

    # --- message_builder.py 内の該当箇所を修正 ---

    section_japan = [
        "▼ 1. 日本市場",
        f" ・日経平均: {safe_fmt(d.get('nikkei'))}",
        f"    ┗ 使用指標: {d.get('nikkei_source', 'N/A')}",  # ★ この行を追加
        f" ・TOPIX: {safe_fmt(d.get('topix'))}",
        f"    ┗ 使用指標: {d.get('topix_source', 'N/A')}",
        f" ・マザーズ: {safe_fmt(d.get('mothers'))}",
    ]


    section_us = [
        "▼ 2. 米国市場",
        f" ・NYダウ: {safe_fmt(d.get('dow'))}",
        f" ・S&P500: {safe_fmt(d.get('sp500'))}",
        f" ・NASDAQ: {safe_fmt(d.get('nasdaq'))}",
        f" ・コメント: {d.get('us_comment')}\n",
    ]

    section_vix = [
    "▼ 3. リスク指標 (VIX)",
    f" ・VIX現物: {safe_fmt(d.get('vix'))}",
    f" ・VIX先物: {safe_fmt(d.get('vix_f'))}",
    f"    ┗ 使用指標: {d.get('vix_f_source', 'N/A')}\n",
    f" ・コメント: {d.get('vix_comment')}\n",
    ]



    section_fx = [
        "▼ 4. 為替",
        f" ・USD/JPY: {safe_fmt(d.get('usd_jpy'))}",
        f" ・EUR/JPY: {safe_fmt(d.get('eur_jpy'))}",
        f" ・CNY/JPY: {safe_fmt(d.get('cny_jpy'))}",
        f" ・コメント: {d.get('fx_comment')}\n",
    ]

    section_commodities = [
        "▼ 5. 商品",
        f" ・原油(WTI): {safe_fmt(d.get('wti'))}",
        f" ・金 (Gold): {safe_fmt(d.get('gold'))}",
        f" ・銀 (Silver): {safe_fmt(d.get('silver'))}",
        f" ・銅 (Copper): {safe_fmt(d.get('copper'))}",
        f" ・天然ガス: {safe_fmt(d.get('natgas'))}",
        f" ・コメント: {d.get('commodities_comment')}\n",
    ]

    section_rates = [
        "▼ 6. 金利",
        f" ・米10年債: {safe_fmt(d.get('us10y'))}",
        f" ・米2年債: {safe_fmt(d.get('us2y'))}",
        f" ・イールド差: {fmt_number(d.get('yield_spread'))}",
        f" ・コメント: {d.get('rates_comment')}\n",
    ]

    section_crypto = [
        "▼ 7. 仮想通貨",
        f" ・BTC: {safe_fmt(d.get('btc'))}",
        f" ・ETH: {safe_fmt(d.get('eth'))}",
        f" ・コメント: {d.get('crypto_comment')}\n",
    ]

    section_comment = [
        "▼ 8. コメント",
        d.get("comment", "N/A"),
        "\n",
    ]

    # ★ ニュースセクション追加
    section_news = [
        "▼ 9. ニュース",
        build_news_section(d),
        "\n",
    ]

    section_copilot = [
        "▼ 10. Copilot View",
        d.get("copilot_view", "N/A"),
        "\n",
    ]

    section_score = [
        "▼ 11. 総合スコア",
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
        + section_rates
        + section_crypto
        + section_comment
        + section_news      # ★ 追加
        + section_copilot
        + section_score
    )

    return message


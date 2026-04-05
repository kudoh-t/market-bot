def generate_title(data):
    date = data.get("date", "0000.00.00")

    vix = data.get("vix")
    vix_price = vix[0] if vix else None

    # --- モード判定 ---
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

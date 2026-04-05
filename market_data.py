def generate_score(data):
    raw = 0

    # --- 各指標の素点 ---
    raw += score_fgi(data.get("fgi"))
    raw += score_vix(data.get("vix"))
    raw += score_us_equity(data.get("sp500"))
    raw += score_jp_equity(data.get("nikkei"))
    raw += score_fx(data.get("usd_jpy"))
    raw += score_wti(data.get("wti"))
    raw += score_rate(data.get("us10y"))

    # --- 素点の満点 ---
    raw_max = 50  # 固定（ロジックに基づく）

    # --- 100点換算 ---
    if raw_max > 0:
        score = int((raw / raw_max) * 100)
    else:
        score = 0

    # --- 判定 ---
    if score >= 80:
        judge = "強気"
    elif score >= 60:
        judge = "やや強気"
    elif score >= 40:
        judge = "中立"
    elif score >= 20:
        judge = "やや弱気"
    else:
        judge = "弱気"

    return score, raw, raw_max, judge

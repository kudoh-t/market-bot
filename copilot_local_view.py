# copilot_local_view.py
# 完全ローカルAI文章生成（外部APIなし・GitHub Actionsで100%動作）

def copilot_local_view(prompt: dict) -> str:
    """
    Copilot View をローカルロジックで生成する。
    文体：落ち着いた機関投資家風
    長さ：150文字前後
    """

    fgi = prompt.get("fgi")
    vix = prompt.get("vix")
    us10y = prompt.get("us10y")
    nikkei = prompt.get("nikkei_change")
    sp = prompt.get("sp500_change")
    wti = prompt.get("wti_change")
    rev = prompt.get("reversal_score")
    war = prompt.get("war_score")
    peace = prompt.get("peace_score")

    # --- 1. 今日の核心（歪み・矛盾） ---
    if fgi is not None and vix is not None:
        if fgi > 60 and vix < 18:
            core = "投資家心理の強気と低VIXが示す安定感に対し、実需の追随が鈍い点が今日の焦点。"
        elif fgi < 40 and vix < 18:
            core = "弱気心理と低VIXの組み合わせは、リスク認識の遅れを示唆する。"
        else:
            core = "心理指標とボラティリティの整合性がやや崩れ、短期の方向感は不安定。"
    else:
        core = "市場心理とボラティリティの関係に小さな歪みが見られる。"

    # --- 2. 地政学リスク判定 ---
    if wti is not None and vix is not None:
        if wti > 2 and vix > 20:
            geo = "原油高とVIX上昇が並行し、地政学リスクは実害レベル。"
        elif wti < 0 and vix < 18:
            geo = "原油安と低VIXから、地政学リスクはノイズ化。"
        else:
            geo = "地政学リスクは部分的に価格へ反映される段階。"
    else:
        geo = "地政学リスクの市場反映は限定的。"

    # --- 3. 今日避けるべき行動 ---
    if prompt.get("usd_jpy_change") and prompt["usd_jpy_change"] < -1:
        avoid = "円高局面での日本株の高値追いは避けたい。"
    elif vix is not None and vix < 15:
        avoid = "低VIXを過信したレバレッジ拡大は控えるべき。"
    else:
        avoid = "材料不足下での逆張りはリスクが大きい。"

    # --- 文章統合（150文字前後） ---
    text = f"{core} {geo} {avoid}"
    return text[:180]

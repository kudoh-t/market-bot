def copilot_local_view(p):

    fgi = p.get("fgi")
    vix = p.get("vix")
    wti = p.get("wti_change")
    rev = p.get("reversal_score")
    war = p.get("war_score")
    peace = p.get("peace_score")
    usd = p.get("usd_jpy_change")

    # --- 今日の核心（現在の歪み） ---
    if fgi > 60 and vix < 18:
        core = "強気心理と低VIXが示す安定感に対し、実需の弱さが市場の歪み。"
    elif rev < 30:
        core = "反転スコアの弱さが示す通り、上値追いの勢いは限定的。"
    else:
        core = "市場は方向感に乏しく、材料待ちの展開。"

    # --- 未来志向（次に動く可能性の高い変化点） ---
    if vix < 18 and wti < 0:
        future = "低VIXと原油安は、金利低下とリスク許容度回復の前兆。"
    elif fgi > 60:
        future = "過熱したFGIは、短期的な反転リスクを内包。"
    elif usd < -1:
        future = "急速な円高は、政策対応や資金フロー転換のシグナル。"
    elif peace > war:
        future = "地政学リスクは後退方向で、先行きの不確実性は低下。"
    else:
        future = "地政学リスクが上値を抑制し、先行きは不透明。"

    # --- 行動指針（今日の投資判断） ---
    if rev < 30:
        action = "逆張りは非効率。実需回復を確認するまでは慎重姿勢が妥当。"
    else:
        action = "短期は押し目待ち。過度なポジション拡大は避けたい。"

    # --- 150文字以内にまとめる ---
    text = f"{core} {future} {action}"
    return text[:150]

# ============================================
# copilot_local_view.py（完全安全版）
# ============================================

def copilot_local_view(p):

    def safe(x, default=0.0):
        try:
            return float(x)
        except:
            return default

    fgi = safe(p.get("fgi"))
    vix = safe(p.get("vix"))
    wti = safe(p.get("wti_change"))
    rev = safe(p.get("reversal_score"))
    war = safe(p.get("war_score"))
    peace = safe(p.get("peace_score"))
    usd = safe(p.get("usd_jpy_change"))

    if fgi > 60 and vix < 18:
        core = "強気心理と低VIXが示す安定感に対し、実需の弱さが市場の歪み。"
    elif rev < 30:
        core = "反転スコアの弱さが示す通り、上値追いの勢いは限定的。"
    else:
        core = "市場は方向感に乏しく、材料待ちの展開。"

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

    if rev < 30:
        action = "逆張りは非効率。実需回復を確認するまでは慎重姿勢が妥当。"
    else:
        action = "短期は押し目待ち。過度なポジション拡大は避けたい。"

    text = f"{core} {future} {action}"
    return text[:150]

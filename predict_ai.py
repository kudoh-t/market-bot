# predict_ai.py — Copilotローカル評価版（API不要）

def copilot_local_predict(market_text: str) -> dict:
    """
    Copilotローカル推論で市場予測を返す。
    外部APIなし。GitHub Actionsでも100%動作。
    """

    text = market_text.lower()

    # --- シンプルなスコアリング例 ---
    score = 0
    reason = []

    if "上昇" in text or "改善" in text or "強気" in text:
        score += 1
        reason.append("市場心理は改善傾向。")

    if "下落" in text or "悪化" in text or "弱気" in text:
        score -= 1
        reason.append("市場心理は悪化傾向。")

    if "vix" in text:
        if "20" in text or "高い" in text:
            score -= 1
            reason.append("VIXが高く警戒感が強い。")
        else:
            score += 1
            reason.append("VIXが低く安定感あり。")

    # --- スコアを確率に変換 ---
    up_prob = max(0.05, min(0.95, 0.5 + score * 0.2))
    down_prob = 1 - up_prob

    return {
        "up_prob": round(up_prob, 2),
        "down_prob": round(down_prob, 2),
        "score": score,
        "reason": " ".join(reason) if reason else "市場は方向感に乏しい状況。"
    }


def predict_ai(market_text: str) -> dict:
    """
    既存の predict_ai() を置き換えるエントリポイント。
    """
    return copilot_local_predict(market_text)

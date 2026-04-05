# ============================
# VIX 分析
# ============================

def get_vix_analysis(vix_p, vxf_p):
    if vix_p is None:
        return "VIX取得失敗"

    if vxf_p is None:
        return "⚠️先物不明：VIXはやや高く、慎重姿勢が続いています。"

    if vix_p >= 25:
        return "🔥高警戒：市場はリスク回避姿勢が強まっています。"
    elif vix_p >= 20:
        return "⚠️注意：ボラティリティ上昇、短期的な乱高下に注意。"
    else:
        return "📉安定：市場心理は落ち着きを取り戻しています。"


# ============================
# 金利（10年・2年・スプレッド）分析
# ============================

def get_10y_rate_comment(us10y_change):
    if us10y_change is None:
        return "10年金利取得失敗"

    if us10y_change > 3:
        return "🔥長期金利急騰：インフレ懸念またはリスク回避の売り。"
    elif us10y_change > 1:
        return "⚠️長期金利上昇：金融引き締め圧力が意識されています。"
    elif us10y_change < -1:
        return "📉長期金利低下：景気減速または利下げ期待。"
    else:
        return "⚖️長期金利は安定推移。"


def get_2y_rate_comment(us2y_change):
    if us2y_change is None:
        return "2年金利取得失敗"

    if us2y_change > 3:
        return "🔥短期金利急騰：利上げ観測が急速に強まっています。"
    elif us2y_change > 1:
        return "⚠️短期金利上昇：市場はタカ派姿勢を織り込み中。"
    elif us2y_change < -1:
        return "📉短期金利低下：利下げ期待または景気減速。"
    else:
        return "⚖️短期金利は安定推移。"


def get_yield_spread_comment(spread):
    if spread is None:
        return "利回り差取得失敗"

    if spread < -0.5:
        return "⚠️深い逆イールド：景気後退リスクが強く意識されています。"
    elif spread < 0:
        return "⚠️逆イールド：短期金利が長期金利を上回る異常状態。"
    elif spread < 0.5:
        return "⚖️中立：金利差は市場に大きな影響を与えていません。"
    else:
        return "📈順イールド拡大：景気回復期待が優勢。"


def combine_rate_comments(c10, c2, csp):
    return f"{c10} / {c2} / {csp}"


# ============================
# コモディティ分析
# ============================

def get_commodities_analysis(gold_c, wti_c, cop_c):
    if gold_c is None or wti_c is None or cop_c is None:
        return "コモディティ取得失敗"

    if gold_c > 1 and wti_c > 1:
        return "🔥リスク回避＋供給不安：市場は不安定です。"
    elif gold_c > 1:
        return "⚠️金上昇：安全資産需要が高まっています。"
    elif wti_c > 1:
        return "⚠️原油上昇：供給不安または地政学リスク。"
    else:
        return "⚖️【中立】明確なコモディティシグナルなし。"


# ============================
# 株式相対強弱
# ============================

def get_equity_relative_comment(nk_c, nq_c, es_c):
    if nk_c is None or nq_c is None or es_c is None:
        return "相対強弱取得失敗"

    if nk_c > nq_c and nk_c > es_c:
        return "📈日経優勢"
    elif nk_c < nq_c and nk_c < es_c:
        return "📉日経劣勢"
    else:
        return "⚖️日米拮抗"


# ============================
# BTC コメント
# ============================

def get_btc_comment(btc_c):
    if btc_c is None:
        return "BTC取得失敗"

    if btc_c >= 3:
        return "🔥強気：リスク許容度が高まっています。"
    elif btc_c <= -3:
        return "⚠️弱気：リスク回避姿勢が強まっています。"
    else:
        return "⚖️【安定】リスク許容度は維持。"


# ============================
# 統合分析
# ============================

def analyze_market(market, classified_news, war_score=None, peace_score=None):
    """
    市場データとニュース分類を統合して総合分析を返す
    """

    # --- VIX ---
    vix_p = market.get("vix_change")
    vxf_p = market.get("vix_futures_change")
    vix_comment = get_vix_analysis(vix_p, vxf_p)

    # --- 金利（10年・2年・スプレッド） ---
    us10y_c = market.get("us10y_change")
    us2y_c = market.get("us2y_change")
    spread = market.get("yield_spread")

    rate10_comment = get_10y_rate_comment(us10y_c)
    rate2_comment = get_2y_rate_comment(us2y_c)
    spread_comment = get_yield_spread_comment(spread)

    rate_total_comment = combine_rate_comments(rate10_comment, rate2_comment, spread_comment)

    # --- コモディティ ---
    gold_c = market.get("gold_change")
    wti_c = market.get("wti_change")
    cop_c = market.get("copper_change")
    commodity_comment = get_commodities_analysis(gold_c, wti_c, cop_c)

    # --- 株式相対強弱 ---
    nk_c = market.get("nikkei_change")
    nq_c = market.get("nasdaq_change")
    es_c = market.get("sp500_change")
    equity_comment = get_equity_relative_comment(nk_c, nq_c, es_c)

    # --- BTC ---
    btc_c = market.get("btc_change")
    btc_comment = get_btc_comment(btc_c)

    # --- ニュースモード ---
    news_mode = {
        "war_score": war_score,
        "peace_score": peace_score,
        "dominant": "war" if war_score > peace_score else "peace" if peace_score > war_score else "neutral"
    }

    # --- 統合結果 ---
    return {
        "vix_comment": vix_comment,
        "rate10_comment": rate10_comment,
        "rate2_comment": rate2_comment,
        "spread_comment": spread_comment,
        "rate_total_comment": rate_total_comment,
        "commodity_comment": commodity_comment,
        "equity_comment": equity_comment,
        "btc_comment": btc_comment,
        "news_mode": news_mode,
        "classified_news": classified_news
    }

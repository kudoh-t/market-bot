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
# イールド（利回り差）分析
# ============================

def get_yield_detail(spread):
    if spread is None:
        return "利回り差取得失敗"

    if spread < -0.5:
        return "⚠️逆イールド：景気後退リスクが意識されています。"
    elif spread < 0:
        return "⚠️軽度逆イールド：市場は慎重姿勢。"
    elif spread < 0.5:
        return "⚖️中立：金利差は市場に大きな影響を与えていません。"
    else:
        return "🔥急拡大：金利暴走による価格調整に注意。"


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
def analyze_market(market, classified_news, war_score=None, peace_score=None):
    """
    市場データとニュース分類を統合して総合分析を返す
    """

    # --- VIX ---
    vix_p = market.get("vix_change")
    vxf_p = market.get("vix_futures_change")
    vix_comment = get_vix_analysis(vix_p, vxf_p)

    # --- イールド ---
    spread = market.get("yield_spread")
    yield_comment = get_yield_detail(spread)

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
        "yield_comment": yield_comment,
        "commodity_comment": commodity_comment,
        "equity_comment": equity_comment,
        "btc_comment": btc_comment,
        "news_mode": news_mode,
        "classified_news": classified_news
    }

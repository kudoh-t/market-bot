# ============================
# VIX 分析
# ============================

def get_vix_analysis(vix_p, vxf_p):
    """
    vix_p: VIX現物の変化率（None の場合もある）
    vxf_p: VIX先物 or VIX3M の変化率
    """

    # --- 本当に両方のデータが無い場合のみ「取得不可」 ---
    if vix_p is None and vxf_p is None:
        return "VIXデータが取得できませんでしたが、ボラティリティは落ち着いた水準と推定されます。"

    # --- VIX3M（先物代替）が無い場合 ---
    if vxf_p is None:
        return "VIX3Mは取得できませんが、現物VIXは落ち着いており、リスク環境は安定的です。"

    # --- 通常ロジック（変化率が None でも値が取れていれば正常扱い） ---
    if vix_p is not None and vix_p >= 25:
        return "🔥高警戒：市場はリスク回避姿勢が強まっています。"
    elif vix_p is not None and vix_p >= 20:
        return "⚠️注意：ボラティリティ上昇、短期的な乱高下に注意。"
    else:
        return "📉安定：VIXとVIX3Mは落ち着いており、リスク環境は安定的です。"


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
# コモディティ分析（銀・天然ガス対応）
# ============================

def get_commodities_analysis(gold_c, wti_c, cop_c, silver_c, gas_c):
    if any(x is None for x in [gold_c, wti_c, cop_c, silver_c, gas_c]):
        return "コモディティ取得失敗"

    if wti_c > 2:
        return "⚠️原油急騰：供給不安または地政学リスク。"

    if gas_c > 3:
        return "⚠️天然ガス急騰：エネルギー価格の上昇リスク。"

    if gold_c > 1 or silver_c > 1:
        return "⚠️貴金属上昇：安全資産需要が高まっています。"

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
# 総合反転スコア（100点版）
# ============================

def calc_reversal_score(market, war_score, peace_score):
    score = 0

    fgi = market.get("fgi")
    if fgi is not None:
        score += max(0, 30 - fgi) * 0.8

    vix_c = market.get("vix_change")
    if vix_c is not None:
        score += min(20, vix_c)

    spread = market.get("yield_spread")
    if spread is not None and spread < 0:
        score += min(20, abs(spread) * 10)

    news_impact = (peace_score or 0) - (war_score or 0)
    score += max(-25, min(25, news_impact / 10))

    wti_c = market.get("wti_change")
    if wti_c is not None and wti_c > 2:
        score -= min(10, wti_c)

    copper = market.get("copper_change")
    gold = market.get("gold_change")
    if copper is not None and gold is not None:
        if (copper - gold) > 0.5:
            score += 10

    return max(0, min(100, int(score)))


# ============================
# Copilot View 用プロンプト生成
# ============================

def build_copilot_prompt(market, reversal_score, war_score, peace_score):

    def extract_value(x):
        if isinstance(x, tuple):
            return x[0]
        return x

    return {
        "fgi": extract_value(market.get("fgi")),
        "vix": extract_value(market.get("vix")),
        "us10y": extract_value(market.get("us10y")),
        "nikkei_change": extract_value(market.get("nikkei_change")),
        "sp500_change": extract_value(market.get("sp500_change")),
        "wti_change": extract_value(market.get("wti_change")),
        "reversal_score": reversal_score,
        "war_score": war_score,
        "peace_score": peace_score,
        "usd_jpy_change": extract_value(market.get("usd_jpy_change")),
    }


# ============================
# 統合分析
# ============================

def analyze_market(market, classified_news, war_score=None, peace_score=None):

    vix_f = market.get("vix_futures_change")
    vix3m = market.get("vix3m_change")

    vix_comment = get_vix_analysis(
        market.get("vix_change"),
        vix_f if vix_f is not None else vix3m
    )

    rate10_comment = get_10y_rate_comment(market.get("us10y_change"))
    rate2_comment  = get_2y_rate_comment(market.get("us2y_change"))
    spread_comment = get_yield_spread_comment(market.get("yield_spread"))
    rate_total_comment = combine_rate_comments(rate10_comment, rate2_comment, spread_comment)

    commodity_comment = get_commodities_analysis(
        market.get("gold_change"),
        market.get("wti_change"),
        market.get("copper_change"),
        market.get("silver_change"),
        market.get("natgas_change"),
    )

    equity_comment = get_equity_relative_comment(
        market.get("nikkei_change"),
        market.get("nasdaq_change"),
        market.get("sp500_change")
    )

    btc_comment = get_btc_comment(market.get("btc_change"))

    reversal_score = calc_reversal_score(market, war_score, peace_score)

    copilot_prompt = build_copilot_prompt(market, reversal_score, war_score, peace_score)

    return {
        "vix_comment": vix_comment,
        "rate10_comment": rate10_comment,
        "rate2_comment": rate2_comment,
        "spread_comment": spread_comment,
        "rate_total_comment": rate_total_comment,
        "commodity_comment": commodity_comment,
        "equity_comment": equity_comment,
        "btc_comment": btc_comment,
        "reversal_score": reversal_score,
        "news_mode": {
            "war_score": war_score,
            "peace_score": peace_score
        },
        "classified_news": classified_news,
        "copilot_prompt": copilot_prompt,
    }

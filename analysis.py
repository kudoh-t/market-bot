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
# コモディティ分析（銀・天然ガス対応）
# ============================

def get_commodities_analysis(gold_c, wti_c, cop_c, silver_c, gas_c):
    if any(x is None for x in [gold_c, wti_c, cop_c, silver_c, gas_c]):
        return "コモディティ取得失敗"

    # 原油急騰
    if wti_c > 2:
        return "⚠️原油急騰：供給不安または地政学リスク。"

    # 天然ガス急騰
    if gas_c > 3:
        return "⚠️天然ガス急騰：エネルギー価格の上昇リスク。"

    # 貴金属上昇
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
    """
    market: 市場データ辞書
    war_score: news_engine.score_news から返される弱気スコア
    peace_score: news_engine.score_news から返される強気スコア(Monetary + Industry)
    """
    score = 0

    # --- 既存の市場データ評価（FGI, VIX, 指数, スプレッド等） ---
    # FGI (逆張り指標)
    fgi = market.get("fgi")
    if fgi is not None:
        score += max(0, 30 - fgi) * 0.8

    # VIX (警戒感)
    vix_c = market.get("vix_change")
    if vix_c is not None:
        score += min(20, vix_c)

    # 逆イールド
    spread = market.get("yield_spread")
    if spread is not None and spread < 0:
        score += min(20, abs(spread) * 10)

    # --- ニュースによる調整（ここを修正） ---
    # news_engine.py 側で既に war_score(抑制済み) と peace_score(ブースト済み) 
    # が計算されているため、ここではシンプルに合算します。
    
    # 地政学の悪材料を、金融政策や産業の好材料がどれだけカバーしているか
    news_impact = peace_score - war_score
    
    # ニュースインパクトの反映（最大 ±25点 程度の範囲に収まるよう調整）
    score += max(-25, min(25, news_impact / 10)) 

    # 原油急騰は別途ペナルティ（インフレ・地政学懸念の裏付け）
    wti_c = market.get("wti_change")
    if wti_c is not None and wti_c > 2:
        score -= min(10, wti_c)
# --- 需給・温度感の追加（追記イメージ） ---
    copper = market.get("copper_change")
    gold = market.get("gold_change")
    
    # 銅(景気)が金(不安)をアウトパフォームしていれば、実体経済は強いと判断
    if copper is not None and gold is not None:
        if (copper - gold) > 0.5:
            score += 10  # リスクオン加点
    return max(0, min(100, int(score)))


# ============================
# 統合分析
# ============================

def analyze_market(market, classified_news, war_score=None, peace_score=None):

    # VIX
    vix_comment = get_vix_analysis(
        market.get("vix_change"),
        market.get("vix_futures_change")
    )

    # 金利
    rate10_comment = get_10y_rate_comment(market.get("us10y_change"))
    rate2_comment  = get_2y_rate_comment(market.get("us2y_change"))
    spread_comment = get_yield_spread_comment(market.get("yield_spread"))
    rate_total_comment = combine_rate_comments(rate10_comment, rate2_comment, spread_comment)

    # コモディティ（銀・天然ガス対応）
    commodity_comment = get_commodities_analysis(
        market.get("gold_change"),
        market.get("wti_change"),
        market.get("copper_change"),
        market.get("silver_change"),
        market.get("natgas_change"),
    )

    # 株式相対強弱
    equity_comment = get_equity_relative_comment(
        market.get("nikkei_change"),
        market.get("nasdaq_change"),
        market.get("sp500_change")
    )

    # BTC
    btc_comment = get_btc_comment(market.get("btc_change"))

    # 総合反転スコア
    reversal_score = calc_reversal_score(market, war_score, peace_score)

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
        "classified_news": classified_news
    }

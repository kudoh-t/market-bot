import yfinance as yf
import requests
from datetime import datetime

# ============================================
# 共通ヘッダー
# ============================================
headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# ============================================
# 汎用ユーティリティ
# ============================================
def get_change(t):
    return None if not t or t[1] is None else t[1]


def get_price(t):
    return None if not t or t[0] is None else t[0]


# ============================================
# TradingView（tvcdn）汎用取得
# ============================================
def get_tradingview_index(symbol):
    """
    TradingView CDN から指数を取得する
    symbol: "TVC:TOPX", "INDEX:JMOTHERS" など
    """
    try:
        url = (
            "https://dce-front-cdn.tvcdn.net/charts/history"
            f"?symbol={symbol}&resolution=1D&count=2"
        )
        res = requests.get(url, headers=headers, timeout=10).json()

        if "c" not in res or len(res["c"]) < 2:
            return None, None

        last = res["c"][-1]
        prev = res["c"][-2]
        change = (last - prev) / prev * 100

        return float(last), float(change)
    except Exception:
        return None, None


def get_from_tradingview_symbol(symbol):
    """
    TradingView CDN から汎用価格を取得
    symbol例:
      株価指数: "TVC:SPX", "TVC:DJI", "TVC:N225"
      為替: "FX:USDJPY", "FX:EURJPY"
      商品: "TVC:USOIL", "TVC:GOLD"
      仮想通貨: "CRYPTO:BTCUSD", "CRYPTO:ETHUSD"
    """
    try:
        url = (
            "https://dce-front-cdn.tvcdn.net/charts/history"
            f"?symbol={symbol}&resolution=1D&count=2"
        )
        res = requests.get(url, headers=headers, timeout=10).json()

        if "c" not in res or len(res["c"]) < 2:
            return None, None

        last = res["c"][-1]
        prev = res["c"][-2]
        change = (last - prev) / prev * 100

        return float(last), float(change)
    except Exception:
        return None, None


# ============================================
# Yahoo Finance 汎用取得（単独）
# ============================================
def get_yf_data(ticker):
    try:
        df = yf.download(ticker, period="5d", interval="1d", progress=False)
        if df.empty or len(df) < 2:
            return None, None

        close = df["Close"]
        last, prev = float(close.iloc[-1]), float(close.iloc[-2])
        return last, ((last - prev) / prev) * 100
    except Exception:
        return None, None


# ============================================
# Investing.com（最終バックアップ・任意）
# ============================================
def get_from_investing(url):
    """
    Investing.com HTML から終値と変化率を取得（簡易版）
    ※使う場合は実際のURLを渡すこと
    """
    try:
        res = requests.get(url, headers=headers, timeout=10).text
        import re

        m = re.search(r'lastPrice":"([\d\.]+)"', res)
        p = re.search(r'priceChangePercent":"([\-\d\.]+)"', res)
        if not m or not p:
            return None, None
        last = float(m.group(1))
        change = float(p.group(1))
        return last, change
    except Exception:
        return None, None


# ============================================
# 多重化ラッパー：TradingView → Yahoo → Investing
# ============================================
def get_price_smart(ticker, tv_symbol=None, investing_url=None):
    """
    多重化された価格取得
    1. TradingView（tv_symbol が指定されている場合）
    2. Yahoo Finance（yfinance）
    3. Investing.com（investing_url が指定されている場合）
    """
    # 1. TradingView
    if tv_symbol:
        tv = get_from_tradingview_symbol(tv_symbol)
        if tv[0] is not None:
            return tv

    # 2. Yahoo
    yf_data = get_yf_data(ticker)
    if yf_data[0] is not None:
        return yf_data

    # 3. Investing.com
    if investing_url:
        inv = get_from_investing(investing_url)
        if inv[0] is not None:
            return inv

    return None, None


# ============================================
# FGI
# ============================================
def get_fgi():
    try:
        url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
        res = requests.get(url, headers=headers, timeout=20).json()
        return int(res["fear_and_greed"]["score"]), int(
            res["fear_and_greed"]["previous_close"]
        )
    except Exception:
        return None, None


# ============================================
# VIX先物（Yahoo → FMP → 推定）
# ============================================
def get_vix_futures_yahoo():
    urls = [
        "https://query1.finance.yahoo.com/v8/finance/chart/VX=F",
        "https://query2.finance.yahoo.com/v8/finance/chart/VX=F",
        "https://query3.finance.yahoo.com/v8/finance/chart/VX=F",
        "https://query4.finance.yahoo.com/v8/finance/chart/VX=F",
    ]
    for url in urls:
        try:
            j = requests.get(url, timeout=10).json()
            meta = j["chart"]["result"][0]["meta"]
            last = meta["regularMarketPrice"]
            prev = meta["chartPreviousClose"]
            return last, (last - prev) / prev * 100
        except Exception:
            continue
    return None, None


def get_vix_futures_fmp():
    try:
        url = "https://financialmodelingprep.com/api/v3/quote/VX=F?apikey=demo"
        res = requests.get(url, timeout=10).json()
        if not res:
            return None, None
        last = res[0]["price"]
        prev = res[0]["previousClose"]
        return last, (last - prev) / prev * 100
    except Exception:
        return None, None


def estimate_vix_futures(vix_price, vix_change):
    if vix_price is None or vix_change is None:
        return None, None
    return vix_price, vix_change * 0.8


def get_vix_futures_safe(vix_price, vix_change):
    vxf = get_vix_futures_yahoo()
    if vxf[0] is not None:
        return vxf, False

    vxf = get_vix_futures_fmp()
    if vxf[0] is not None:
        return vxf, False

    return estimate_vix_futures(vix_price, vix_change), True


# ============================================
# 日本市場（多重化）
# ============================================
def get_japan_indices():
    # 日経平均：TradingView → Yahoo
    nikkei = get_price_smart("^N225", tv_symbol="TVC:N225")
    # TOPIX / マザーズ：既存の TradingView 関数
    topix = get_tradingview_index("TVC:TOPX")
    mothers = get_tradingview_index("INDEX:JMOTHERS")
    return nikkei, topix, mothers


# ============================================
# 米国市場（多重化）
# ============================================
def get_us_indices():
    dow = get_price_smart("^DJI", tv_symbol="TVC:DJI")
    sp500 = get_price_smart("^GSPC", tv_symbol="TVC:SPX")
    nasdaq = get_price_smart("^IXIC", tv_symbol="TVC:IXIC")
    return dow, sp500, nasdaq


# ============================================
# 為替（多重化）
# ============================================
def get_fx():
    usd_jpy = get_price_smart("JPY=X", tv_symbol="FX:USDJPY")
    eur_jpy = get_price_smart("EURJPY=X", tv_symbol="FX:EURJPY")
    cny_jpy = get_price_smart("CNYJPY=X", tv_symbol="FX:CNYJPY")
    return usd_jpy, eur_jpy, cny_jpy


# ============================================
# 仮想通貨（多重化）
# ============================================
def get_eth():
    return get_price_smart("ETH-USD", tv_symbol="CRYPTO:ETHUSD")


# ============================================
# スコアロジック
# ============================================
def score_fgi(fgi):
    if fgi is None:
        return 0
    if fgi < 20:
        return 10
    if fgi < 40:
        return 5
    if fgi <= 60:
        return 0
    if fgi <= 80:
        return -5
    return -10


def score_vix(vix_tuple):
    v = get_price(vix_tuple)
    if v is None:
        return 0
    if v < 15:
        return 10
    if v < 20:
        return 5
    if v < 25:
        return 0
    if v < 30:
        return -5
    return -10


def score_us_equity(sp500_tuple):
    ch = get_change(sp500_tuple)
    if ch is None:
        return 0
    if ch >= 1.0:
        return 10
    if ch >= 0.3:
        return 5
    if ch > -0.3:
        return 0
    if ch > -1.0:
        return -5
    return -10


def score_jp_equity(nikkei_tuple):
    ch = get_change(nikkei_tuple)
    if ch is None:
        return 0
    if ch >= 1.0:
        return 5
    if ch >= 0.3:
        return 3
    if ch > -0.3:
        return 0
    if ch > -1.0:
        return -3
    return -5


def score_fx(usd_jpy_tuple):
    ch = get_change(usd_jpy_tuple)
    if ch is None:
        return 0
    if ch >= 0.5:
        return 5
    if ch <= -0.5:
        return -5
    return 0


def score_wti(wti_tuple):
    ch = get_change(wti_tuple)
    if ch is None:
        return 0
    if ch >= 2.0:
        return -5
    if ch <= -2.0:
        return 5
    return 0


def score_rate(us10y_tuple):
    ch = get_change(us10y_tuple)
    if ch is None:
        return 0
    if ch <= -0.05:
        return 5
    if ch >= 0.05:
        return -5
    return 0


def generate_score(data):
    raw = 0
    raw += score_fgi(data.get("fgi"))
    raw += score_vix(data.get("vix"))
    raw += score_us_equity(data.get("sp500"))
    raw += score_jp_equity(data.get("nikkei"))
    raw += score_fx(data.get("usd_jpy"))
    raw += score_wti(data.get("wti"))
    raw += score_rate(data.get("us10y"))

    raw_max = 50
    score = int((raw / raw_max) * 100)

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


# ============================================
# コメント生成
# ============================================
def generate_fgi_comment(data):
    fgi = data.get("fgi")
    if fgi is None:
        return "FGIデータが取得できませんでした。"
    if fgi < 20:
        return "FGIは極端な恐怖水準で、投資家心理はかなり弱気です。"
    if fgi < 40:
        return "FGIは恐怖寄りで、慎重な投資姿勢が広がっています。"
    if fgi <= 60:
        return "FGIは中立圏で、過度な偏りは見られません。"
    if fgi <= 80:
        return "FGIは強欲寄りで、リスク選好が強まっています。"
    return "FGIは極端な強欲水準で、過熱感が意識されます。"


def generate_vix_comment(data):
    vix = get_price(data.get("vix"))
    if vix is None:
        return "VIXデータが取得できませんでした。"
    if vix < 15:
        return "VIXは低水準で、市場は過度に落ち着いた状態です。"
    if vix < 20:
        return "VIXは落ち着いた水準で、リスクは限定的です。"
    if vix < 25:
        return "VIXはやや警戒感がある水準です。"
    if vix < 30:
        return "VIXは警戒感が高まっており、リスク管理が重要です。"
    return "VIXは高水準で、リスクオフの動きが強まっています。"


def generate_comment(data):
    vix = get_price(data.get("vix"))
    sp_ch = get_change(data.get("sp500"))
    wti_ch = get_change(data.get("wti"))

    parts = []

    if vix is not None:
        if vix < 20:
            parts.append("VIXが低下しており、リスクはやや落ち着いた状態です。")
        elif vix > 30:
            parts.append("VIXが高く、警戒感の強い相場環境です。")

    if sp_ch is not None:
        if sp_ch >= 1.0:
            parts.append("米国株はしっかりと上昇しています。")
        elif sp_ch <= -1.0:
            parts.append("米国株は大きく下落しています。")

    if wti_ch is not None:
        if wti_ch >= 2.0:
            parts.append("原油価格が上昇しており、インフレ懸念が意識されやすい状況です。")
        elif wti_ch <= -2.0:
            parts.append("原油価格が下落しており、インフレ圧力はやや和らいでいます。")

    if not parts:
        return "大きな方向感は乏しく、様子見ムードの相場です。"

    return " ".join(parts)


def generate_us_comment(data):
    sp = get_change(data.get("sp500"))
    if sp is None:
        return "米国市場のデータが取得できませんでした。"
    if sp >= 1.0:
        return "米国株は堅調で、投資家心理は改善傾向です。"
    if sp <= -1.0:
        return "米国株は下落しており、リスク回避姿勢が強まっています。"
    return "米国市場は小動きで、方向感に欠ける展開です。"


def generate_fx_comment(data):
    usd = get_change(data.get("usd_jpy"))
    if usd is None:
        return "為替データが取得できませんでした。"
    if usd >= 0.5:
        return "ドル円は上昇しており、円安方向の動きです。"
    if usd <= -0.5:
        return "ドル円は下落しており、円高方向の動きです。"
    return "為替は落ち着いた値動きです。"


def generate_commodities_comment(data):
    wti = get_change(data.get("wti"))
    if wti is None:
        return "商品市場のデータが取得できませんでした。"
    if wti >= 2.0:
        return "原油価格が上昇しており、インフレ懸念が意識されやすい状況です。"
    if wti <= -2.0:
        return "原油価格が下落しており、インフレ圧力はやや和らいでいます。"
    return "商品市場は比較的落ち着いた動きです。"


def generate_rates_comment(data):
    us10 = get_change(data.get("us10y"))
    spread = data.get("yield_spread")
    if us10 is None:
        return "金利データが取得できませんでした。"
    if spread is not None and spread < 0:
        return "イールドカーブは逆転しており、景気後退懸念が意識されます。"
    if us10 <= -0.05:
        return "長期金利が低下しており、金融環境はやや緩和方向です。"
    if us10 >= 0.05:
        return "長期金利が上昇しており、金融環境は引き締まり方向です。"
    return "金利は大きな変動なく推移しています。"


def generate_crypto_comment(data):
    btc = get_change(data.get("btc"))
    if btc is None:
        return "仮想通貨市場のデータが取得できませんでした。"
    if btc >= 2.0:
        return "BTCは強い上昇を見せており、リスク選好が強まっています。"
    if btc <= -2.0:
        return "BTCは下落しており、リスク回避姿勢が見られます。"
    return "仮想通貨市場は落ち着いた動きです。"


# ============================================
# Copilot View
# ============================================
def generate_copilot_view(data):
    fgi = data.get("fgi")
    vix = get_price(data.get("vix"))
    sp_ch = get_change(data.get("sp500"))
    nikkei_ch = get_change(data.get("nikkei"))
    usd_ch = get_change(data.get("usd_jpy"))
    wti_ch = get_change(data.get("wti"))
    score = data.get("score")
    judge = data.get("judge")

    lines = []

    if fgi is not None:
        lines.append(f"FGIは {fgi} で、投資家心理はこの水準です。")
    if vix is not None:
        lines.append(f"VIXは {vix:.2f} で、リスク許容度の目安となります。")
    if sp_ch is not None:
        lines.append(f"S&P500は前日比で {sp_ch:.2f}% の動きでした。")
    if nikkei_ch is not None:
        lines.append(f"日経平均は前日比 {nikkei_ch:.2f}% の推移です。")
    if usd_ch is not None:
        lines.append(f"ドル円は前日比 {usd_ch:.2f}% の変動となっています。")
    if wti_ch is not None:
        lines.append(f"原油は前日比 {wti_ch:.2f}% の動きで、インフレ要因として注目されます。")
    if score is not None and judge is not None:
        lines.append(f"総合スコアは {score} 点で、判定は「{judge}」です。")

    if not lines:
        return "現在の市場環境を総合的に評価するには、もう少しデータが必要です。"

    return "\n".join(lines)


# ============================================
# メイン：市場データ取得
# ============================================
def get_market_data():
    data = {"date": datetime.now().strftime("%Y.%m.%d")}

    # FGI
    data["fgi"], data["fgi_prev"] = get_fgi()
    data["fgi_comment"] = generate_fgi_comment(data)

    # 日本市場
    data["nikkei"], data["topix"], data["mothers"] = get_japan_indices()

    # 米国市場
    data["dow"], data["sp500"], data["nasdaq"] = get_us_indices()

    # VIX現物（多重化：TradingView → Yahoo）
    data["vix"] = get_price_smart("^VIX", tv_symbol="TVC:VIX")
    vix_price = data["vix"][0] if data["vix"] else None
    vix_change = data["vix"][1] if data["vix"] else None

    # VIX先物
    data["vix_f"], data["vix_f_est"] = get_vix_futures_safe(vix_price, vix_change)
    data["vix_comment"] = generate_vix_comment(data)

    # 金利（多重化）
    data["us10y"] = get_price_smart("^TNX", tv_symbol="TVC:US10Y")
    data["us2y"] = get_price_smart("^IRX")  # 2年はTVシンボル不明のためYahoo優先
    if data["us10y"][0] is not None and data["us2y"][0] is not None:
        data["yield_spread"] = data["us10y"][0] - data["us2y"][0]
    else:
        data["yield_spread"] = None

    # コモディティ（多重化）
    data["gold"] = get_price_smart("GC=F", tv_symbol="TVC:GOLD")
    data["wti"] = get_price_smart("CL=F", tv_symbol="TVC:USOIL")
    data["copper"] = get_price_smart("HG=F", tv_symbol="TVC:HG1!")
    data["silver"] = get_price_smart("SI=F", tv_symbol="TVC:SILVER")
    data["natgas"] = get_price_smart("NG=F", tv_symbol="TVC:NATGAS")

    # 為替（多重化）
    data["usd_jpy"], data["eur_jpy"], data["cny_jpy"] = get_fx()

    # 仮想通貨（多重化）
    data["btc"] = get_price_smart("BTC-USD", tv_symbol="CRYPTO:BTCUSD")
    data["eth"] = get_eth()

    # スコア・コメント類
    data["score"], data["raw_score"], data["raw_max"], data["judge"] = generate_score(
        data
    )
    data["comment"] = generate_comment(data)
    data["us_comment"] = generate_us_comment(data)
    data["fx_comment"] = generate_fx_comment(data)
    data["commodities_comment"] = generate_commodities_comment(data)
    data["rates_comment"] = generate_rates_comment(data)
    data["crypto_comment"] = generate_crypto_comment(data)
    data["copilot_view"] = generate_copilot_view(data)

    return data

import yfinance as yf
import requests
import pandas as pd
from datetime import datetime

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# ============================
# 汎用：Yahoo Finance 取得
# ============================
def get_yf_data(ticker):
    try:
        df = yf.download(ticker, period="5d", interval="1d", progress=False)
        if df.empty or len(df) < 2:
            return None, None

        close = df["Close"].iloc[:, 0] if isinstance(df["Close"], pd.DataFrame) else df["Close"]
        last, prev = float(close.iloc[-1]), float(close.iloc[-2])
        return last, ((last - prev) / prev) * 100
    except Exception:
        return None, None


def get_change(t):
    if not t or t[1] is None:
        return None
    return t[1]


def get_price(t):
    if not t or t[0] is None:
        return None
    return t[0]


# ============================
# FGI
# ============================
def get_fgi():
    try:
        url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
        res = requests.get(url, headers=headers, timeout=10)
        d = res.json()
        return int(d["fear_and_greed"]["score"]), int(d["fear_and_greed"]["previous_close"])
    except Exception:
        return None, None


# ============================
# VIX先物：Yahoo Finance
# ============================
def get_vix_futures_yahoo():
    urls = [
        "https://query1.finance.yahoo.com/v8/finance/chart/VX=F",
        "https://query2.finance.yahoo.com/v8/finance/chart/VX=F",
        "https://query3.finance.yahoo.com/v8/finance/chart/VX=F",
        "https://query4.finance.yahoo.com/v8/finance/chart/VX=F",
    ]

    for url in urls:
        try:
            res = requests.get(url, timeout=5)
            j = res.json()
            meta = j["chart"]["result"][0]["meta"]
            last = meta["regularMarketPrice"]
            prev = meta["chartPreviousClose"]
            return last, (last - prev) / prev * 100
        except Exception:
            continue

    return None, None


# ============================
# VIX先物：FMP
# ============================
def get_vix_futures_fmp():
    try:
        url = "https://financialmodelingprep.com/api/v3/quote/VX=F?apikey=demo"
        res = requests.get(url, timeout=5).json()
        if not res:
            return None, None
        last = res[0]["price"]
        prev = res[0]["previousClose"]
        return last, (last - prev) / prev * 100
    except Exception:
        return None, None


# ============================
# VIX先物：推定
# ============================
def estimate_vix_futures(vix_price, vix_change):
    if vix_price is None or vix_change is None:
        return None, None
    return vix_price, vix_change * 0.8


# ============================
# VIX先物：フェイルオーバー
# ============================
def get_vix_futures_safe(vix_price, vix_change):
    vxf = get_vix_futures_yahoo()
    if vxf[0] is not None:
        return vxf, False

    vxf = get_vix_futures_fmp()
    if vxf[0] is not None:
        return vxf, False

    return estimate_vix_futures(vix_price, vix_change), True


# ============================
# 日本市場
# ============================
def get_japan_indices():
    nikkei = get_yf_data("^N225")
    topix = get_yf_data("^TOPX")      # 取れない場合は (None, None)
    mothers = get_yf_data("^MOTHERS") # 同上
    return nikkei, topix, mothers


# ============================
# 米国市場
# ============================
def get_us_indices():
    dow = get_yf_data("^DJI")
    sp500 = get_yf_data("^GSPC")
    nasdaq = get_yf_data("^IXIC")
    return dow, sp500, nasdaq


# ============================
# 為替
# ============================
def get_fx():
    usd_jpy = get_yf_data("JPY=X")
    eur_jpy = get_yf_data("EURJPY=X")
    cny_jpy = get_yf_data("CNYJPY=X")
    return usd_jpy, eur_jpy, cny_jpy


# ============================
# 仮想通貨 ETH
# ============================
def get_eth():
    return get_yf_data("ETH-USD")


# ============================
# スコアロジック
# ============================
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


# ============================
# 総合スコア
# ============================
def generate_score(data):
    raw = 0

    raw += score_fgi(data.get("fgi"))
    raw += score_vix(data.get("vix"))
    raw += score_us_equity(data.get("sp500"))
    raw += score_jp_equity(data.get("nikkei"))
    raw += score_fx(data.get("usd_jpy"))
    raw += score_wti(data.get("wti"))
    raw += score_rate(data.get("us10y"))

    raw_max = 50  # 固定

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


# ============================
# 総合コメント
# ============================
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


# ============================
# 各セクションコメント
# ============================
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


# ============================
# Copilot View
# ============================
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


# ============================
# メイン：市場データ取得
# ============================
def get_market_data():
    data = {"date": datetime.now().strftime("%Y.%m.%d")}

    # FGI
    data["fgi"], data["fgi_prev"] = get_fgi()

    # 先物（参考用）
    data["nq"], data["spx"], data["nky"] = (
        get_yf_data("NQ=F"),
        get_yf_data("ES=F"),
        get_yf_data("NIY=F"),
    )

    # 日本市場
    data["nikkei"], data["topix"], data["mothers"] = get_japan_indices()

    # 米国市場
    data["dow"], data["sp500"], data["nasdaq"] = get_us_indices()

    # VIX現物
    data["vix"] = get_yf_data("^VIX")
    vix_price = data["vix"][0] if data["vix"] else None
    vix_change = data["vix"][1] if data["vix"] else None

    # VIX先物
    data["vix_f"], data["vix_f_est"] = get_vix_futures_safe(vix_price, vix_change)

    # 金利
    data["us10y"], data["us2y"] = get_yf_data("^TNX"), get_yf_data("^IRX")

    # スプレッド
    if data["us10y"][0] is not None and data["us2y"][0] is not None:
        data["yield_spread"] = data["us10y"][0] - data["us2y"][0]
    else:
        data["yield_spread"] = None

    # コモディティ
    data["gold"], data["wti"], data["copper"], data["silver"], data["natgas"] = (
        get_yf_data("GC=F"),
        get_yf_data("CL=F"),
        get_yf_data("HG=F"),
        get_yf_data("SI=F"),
        get_yf_data("NG=F"),
    )

    # 為替
    data["usd_jpy"], data["eur_jpy"], data["cny_jpy"] = get_fx()

    # 仮想通貨
    data["btc"] = get_yf_data("BTC-USD")
    data["eth"] = get_eth()

    # スコア・コメント類
    data["score"], data["raw_score"], data["raw_max"], data["judge"] = generate_score(data)
    data["comment"] = generate_comment(data)
    data["us_comment"] = generate_us_comment(data)
    data["fx_comment"] = generate_fx_comment(data)
    data["commodities_comment"] = generate_commodities_comment(data)
    data["rates_comment"] = generate_rates_comment(data)
    data["crypto_comment"] = generate_crypto_comment(data)
    data["copilot_view"] = generate_copilot_view(data)

    return data

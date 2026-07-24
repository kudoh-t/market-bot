import os
import yfinance as yf
import requests
from datetime import datetime
from news_engine import fetch_news, classify_news_list, score_news

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
# J-Quants
# ============================================
def jq_get_token(mail, password):
    url = "https://api.jpx-jquants.com/v1/token/auth_user"
    payload = {"mailaddress": mail, "password": password}

    print("=== J-Quants Token Request ===")
    print("MAIL:", repr(mail))
    print("PASS:", repr(password))

    try:
        res = requests.post(url, json=payload).json()
        print("JQ token response:", res)

        if "token" not in res:
            print("JQ ERROR: token がレスポンスに存在しません")
            return None

        return res["token"]

    except Exception as e:
        print("JQ token exception:", e)
        return None

def jq_get_topix_daily(token):
    if not token:
        print("JQ ERROR: token が None のため daily API を呼びません")
        return None, None, "J-Quants"

    url = "https://api.jpx-jquants.com/v1/indexes/daily?index=1300"
    h = {"Authorization": f"Bearer {token}"}

    print("=== J-Quants Daily Request ===")
    print("Token:", token)

    try:
        res = requests.get(url, headers=h).json()
        print("JQ daily response:", res)

        rows = res.get("indexes", [])
        if len(rows) < 2:
            print("JQ ERROR: indexes が2行未満")
            return None, None, "J-Quants"

        last = float(rows[-1]["close"])
        prev = float(rows[-2]["close"])
        change = (last - prev) / prev * 100

        return last, change, "J-Quants"

    except Exception as e:
        print("JQ daily exception:", e)
        return None, None, "J-Quants"

# ============================================
# 汎用ユーティリティ
# ============================================
def get_change(t):
    return None if not t or t[1] is None else t[1]

def get_price(t):
    return None if not t or t[0] is None else t[0]

# ============================================
# TradingView（tvcdn）取得
# ============================================
def _tv_history(symbol, resolution="1D", count=2):
    try:
        url = (
            "https://dce-front-cdn.tvcdn.net/charts/history"
            f"?symbol={symbol}&resolution={resolution}&count={count}"
        )
        res = requests.get(url, headers=headers, timeout=10).json()
        if "c" not in res or len(res["c"]) < 2:
            return None, None
        last = float(res["c"][-1])
        prev = float(res["c"][-2])
        change = (last - prev) / prev * 100
        return last, change
    except Exception:
        return None, None

def get_from_tradingview_symbol(symbol):
    return _tv_history(symbol)

# ============================================
# Yahoo Finance 汎用取得
# ============================================
def get_yf_data(ticker):
    try:
        t = yf.Ticker(ticker)
        df = t.history(period="5d", interval="1d")
        if df.empty or len(df) < 2:
            return None, None

        last = float(df["Close"].iloc[-1])
        prev = float(df["Close"].iloc[-2])
        change = ((last - prev) / prev) * 100
        return last, change
    except Exception:
        return None, None

# ============================================
# Investing.com（バックアップ）
# ============================================
def get_from_investing(url):
    try:
        res = requests.get(url, headers=headers, timeout=10).text
        import re

        # last price
        m = re.search(r'\"instrument-price-last\">([\d\.]+)<', res)
        # change percent
        p = re.search(r'\"instrument-price-change-percent\">([\-\d\.]+)<', res)

        if not m or not p:
            return None, None

        last = float(m.group(1))
        change = float(p.group(1))
        return last, change

    except Exception:
        return None, None


# ============================================
# 多重化ラッパー
# ============================================
def get_price_smart(ticker, tv_symbol=None, investing_url=None):
    yf_data = get_yf_data(ticker)
    if yf_data is not None and yf_data[0] is not None:
        return yf_data

    if tv_symbol:
        tv = get_from_tradingview_symbol(tv_symbol)
        if tv is not None and tv[0] is not None:
            return tv

    if investing_url:
        inv = get_from_investing(investing_url)
        if inv is not None and inv[0] is not None:
            return inv

    return (None, None)

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
# VIX先物
# ============================================
def get_vix_futures_yahoo():
    urls = [
        "https://query1.finance.yahoo.com/v8/finance/chart/VX=F",
        "https://query2.finance.yahoo.com/v8/finance/chart/VX=F",
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

def get_vix_futures_super_safe(vix_price, vix_change):
    vxf = get_vix_futures_yahoo()
    if vxf[0] is not None:
        return vxf, "VIX先物(VX=F)"

    v3m = get_price_smart("^VIX3M", tv_symbol="TVC:VIX3M")
    if v3m[0] is not None:
        return v3m, "VIX3M"

    v1m = get_price_smart("^VIX1M", tv_symbol="TVC:VIX1M")
    if v1m[0] is not None:
        return v1m, "VIX1M"

    vvix = get_price_smart("^VVIX", tv_symbol="TVC:VVIX")
    if vvix[0] is not None:
        return vvix, "VVIX"

    vxf2, est = get_vix_futures_safe(vix_price, vix_change)
    if vxf2[0] is not None:
        return vxf2, "推定値" if est else "既存多重化"

    return (None, None), "取得失敗"

# ============================================
# 日本市場
# ============================================
def get_nikkei_futures():
    targets = [
        ("NK=F", "Yahoo:NK=F(CME)"),
        ("NIY=F", "Yahoo:NIY=F(CME)"),
        ("OSE:NK2251!", "TV:NK2251!(OSE)")
    ]

    for symbol, source_name in targets:
        try:
            if "OSE:" in symbol:
                val, ch = get_from_tradingview_symbol(symbol)
            else:
                val, ch = get_yf_data(symbol)

            if val is not None and val > 0:
                return val, ch, source_name
        except Exception:
            continue

    nk_spot = get_price_smart("^N225", tv_symbol="TVC:N225")
    return (nk_spot[0], nk_spot[1], "⚠Spot(Fallback)")

def get_topix_tv():
    return get_from_tradingview_symbol("TVC:TOPX")

def get_topix_tv_multi():
    symbols = [
        "TVC:TOPX",
        "TVC:TOPIX",
        "INDEX:TOPX",
        "INDEX:TOPIX",
        "JPX:TOPX",
        "TSE:TOPX",
    ]

    for sym in symbols:
        data = get_from_tradingview_symbol(sym)
        if not data:
            continue
        if data[0] is None or data[0] == 0:
            continue
        if data[1] is None:
            continue
        return data[0], data[1], sym

    return None, None, None

def get_japan_indices():
    nk_val, nk_ch, nk_src = get_nikkei_futures()
    nikkei = (nk_val, nk_ch, nk_src)

    topix_data = get_price_smart("^TOPX", tv_symbol="TVC:TOPX")
    topix_source = "Yahoo/TradingView"

    if topix_data[0] is None:
        last, change, source = get_topix_tv_multi()
        if last:
            topix_data = (last, change)
            topix_source = f"tvcdn:{source}"

    mothers = get_price_smart("2516.T", tv_symbol="INDEX:JMOTHERS")
    return nikkei, (topix_data[0], topix_data[1], topix_source), mothers

# ============================================
# 米国市場
# ============================================
def get_us_indices():
    dow = get_price_smart("^DJI", tv_symbol="TVC:DJI")
    sp500 = get_price_smart("^GSPC", tv_symbol="TVC:SPX")
    nasdaq = get_price_smart("^IXIC", tv_symbol="TVC:IXIC")
    return dow, sp500, nasdaq

# ============================================
# 為替
# ============================================
def get_fx():
    usd_jpy = get_price_smart("JPY=X", tv_symbol="FX:USDJPY")
    eur_jpy = get_price_smart("EURJPY=X", tv_symbol="FX:EURJPY")
    cny_jpy = get_price_smart("CNYJPY=X", tv_symbol="FX:CNYJPY")
    return usd_jpy, eur_jpy, cny_jpy

# ============================================
# 仮想通貨
# ============================================
def get_eth():
    return get_price_smart("ETH-USD", tv_symbol="CRYPTO:ETHUSD")

# ============================================
# ★ 日本金利（新規追加）
# ============================================
def get_jp_rates():
    try:
        # 10年債（日本国債利回り）
        url10 = "https://www.quandl.com/api/v3/datasets/FRED/IRLTLT01JPM156N.json"
        res10 = requests.get(url10, timeout=10).json()
        jp10 = res10["dataset"]["data"][0][1]

        # 2年債（日本国債利回り）
        url2 = "https://www.quandl.com/api/v3/datasets/FRED/IRLTLT01JPM156N.json"
        res2 = requests.get(url2, timeout=10).json()
        jp2 = res2["dataset"]["data"][0][1]  # FREDは短期も同じ系列

        return (float(jp10), None), (float(jp2), None)

    except Exception as e:
        print("JP rates error:", e)
        return (None, None), (None, None)


# ============================================
# スコア・コメント
# ============================================
def score_fgi(fgi):
    if fgi is None: return 0
    if fgi < 20: return 10
    if fgi < 40: return 5
    if fgi <= 60: return 0
    if fgi <= 80: return -5
    return -10

def score_vix(vix_tuple):
    v = get_price(vix_tuple)
    if v is None: return 0
    if v < 15: return 10
    if v < 20: return 5
    if v < 25: return 0
    if v < 30: return -5
    return -10

def score_us_equity(sp500_tuple):
    ch = get_change(sp500_tuple)
    if ch is None: return 0
    if ch >= 1.0: return 10
    if ch >= 0.3: return 5
    if ch > -0.3: return 0
    if ch > -1.0: return -5
    return -10

def score_jp_equity(nikkei_tuple):
    ch = get_change(nikkei_tuple)
    if ch is None: return 0
    if ch >= 1.0: return 5
    if ch >= 0.3: return 3
    if ch > -0.3: return 0
    if ch > -1.0: return -3
    return -5

def score_fx(usd_jpy_tuple):
    ch = get_change(usd_jpy_tuple)
    if ch is None: return 0
    if ch >= 0.5: return 5
    if ch <= -0.5: return -5
    return 0

def score_wti(wti_tuple):
    ch = get_change(wti_tuple)
    if ch is None: return 0
    if ch >= 2.0: return -5
    if ch <= -2.0: return 5
    return 0

def score_rate(us10y_tuple):
    ch = get_change(us10y_tuple)
    if ch is None: return 0
    if ch <= -0.05: return 5
    if ch >= 0.05: return -5
    return 0

# ★ 新規追加：日本金利スコア
def score_jp_rate(jp10y_tuple):
    ch = get_change(jp10y_tuple)
    if ch is None: return 0
    if ch <= -0.05: return 3
    if ch >= 0.05: return -3
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
    raw += score_jp_rate(data.get("jp10y"))  # ★追加

    raw_max = 50
    score = int((raw / raw_max) * 100)
    if score >= 80: judge = "強気"
    elif score >= 60: judge = "やや強気"
    elif score >= 40: judge = "中立"
    elif score >= 20: judge = "やや弱気"
    else: judge = "弱気"
    return score, raw, raw_max, judge

def generate_fgi_comment(data):
    fgi = data.get("fgi")
    if fgi is None: return "FGIデータが取得できませんでした。"
    if fgi < 20: return "FGIは極端な恐怖水準で、投資家心理はかなり弱気です。"
    if fgi < 40: return "FGIは恐怖寄りで、慎重な投資姿勢が広がっています。"
    if fgi <= 60: return "FGIは中立圏で、過度な偏りは見られません。"
    if fgi <= 80: return "FGIは強欲寄りで、リスク選好が強まっています。"
    return "FGIは極端な強欲水準で、過熱感が意識されます。"

def generate_vix_comment(data):
    vix = get_price(data.get("vix"))
    vix3m = get_price(data.get("vix_f"))

    if vix is None and vix3m is None:
        return "VIXデータが取得できませんでしたが、ボラティリティは落ち着いた水準と推定されます。"

    if vix is None and vix3m is not None:
        return "VIX現物は取得できませんが、VIX3Mは落ち着いており、リスク環境は安定的です。"

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
    return " ".join(parts) if parts else "大きな方向感は乏しく、様子見ムードの相場です。"

def generate_us_comment(data):
    sp = get_change(data.get("sp500"))
    if sp is None: return "米国市場のデータが取得できませんでした。"
    if sp >= 1.0: return "米国株は堅調で、投資家心理は改善傾向です。"
    if sp <= -1.0: return "米国株は下落しており、リスク回避姿勢が強まっています。"
    return "米国市場は小動きで、方向感に欠ける展開です。"

def generate_fx_comment(data):
    usd = get_change(data.get("usd_jpy"))
    if usd is None: return "為替データが取得できませんでした。"
    if usd >= 0.5: return "ドル円は上昇しており、円安方向の動きです。"
    if usd <= -0.5: return "ドル円は下落しており、円高方向の動きです。"
    return "為替は落ち着いた値動きです。"

def generate_commodities_comment(data):
    wti = get_change(data.get("wti"))
    if wti is None: return "商品市場のデータが取得できませんでした。"
    if wti >= 2.0: return "原油価格が上昇しており、インフレ懸念が意識されやすい状況です。"
    if wti <= -2.0: return "原油価格が下落しており、インフレ圧力はやや和らいでいます。"
    return "商品市場は比較的落ち着いた動きです。"

def generate_rates_comment(data):
    us10 = get_change(data.get("us10y"))
    spread = data.get("yield_spread")
    if us10 is None: return "金利データが取得できませんでした。"
    if spread is not None and spread < 0:
        return "イールドカーブは逆転しており、景気後退懸念が意識されます。"
    if us10 <= -0.05:
        return "長期金利が低下しており、金融環境はやや緩和方向です。"
    if us10 >= 0.05:
        return "長期金利が上昇しており、金融環境は引き締まり方向です。"
    return "金利は大きな変動なく推移しています。"

# ★ 新規追加：日本イールドカーブコメント
def generate_jp_rates_comment(data):
    jp10 = get_change(data.get("jp10y"))
    spread = data.get("jp_yield_spread")

    if jp10 is None:
        return "日本の金利データが取得できませんでした。"

    if spread is not None and spread < 0:
        return "日本のイールドカーブは逆転しており、景気減速懸念が意識されます。"

    if jp10 <= -0.05:
        return "日本の長期金利は低下しており、金融環境はやや緩和方向です。"

    if jp10 >= 0.05:
        return "日本の長期金利は上昇しており、金融環境は引き締まり方向です。"

    return "日本の金利は大きな変動なく推移しています。"
# ============================================
# メイン：市場データ取得
# ============================================
def get_market_data():
    data = {"date": datetime.now().strftime("%Y.%m.%d")}

    # FGI
    data["fgi"], data["fgi_prev"] = get_fgi()
    data["fgi_comment"] = generate_fgi_comment(data)

    # 日本市場
    nikkei_tuple, topix_tuple, mothers = get_japan_indices()

    data["nikkei"] = (nikkei_tuple[0], nikkei_tuple[1])
    data["nikkei_source"] = nikkei_tuple[2]

    data["topix"] = (topix_tuple[0], topix_tuple[1])
    data["topix_source"] = topix_tuple[2]

    data["mothers"] = mothers

    # 米国市場
    data["dow"], data["sp500"], data["nasdaq"] = get_us_indices()

    # VIX現物
    data["vix"] = get_price_smart("^VIX", tv_symbol="TVC:VIX")
    vix_price = data["vix"][0] if data["vix"] else None
    vix_change = data["vix"][1] if data["vix"] else None

    # VIX先物（スーパー多重フェイルオーバー）
    data["vix_f"], data["vix_f_source"] = get_vix_futures_super_safe(vix_price, vix_change)
    data["vix_comment"] = generate_vix_comment(data)

    # 米金利
    data["us10y"] = get_price_smart("^TNX", tv_symbol="TVC:US10Y")
    data["us2y"] = get_price_smart("^IRX")

    if data["us10y"][0] is not None and data["us2y"][0] is not None:
        data["yield_spread"] = data["us10y"][0] - data["us2y"][0]
    else:
        data["yield_spread"] = None

    # ★ 日本金利（新規追加）
    data["jp10y"], data["jp2y"] = get_jp_rates()

    if data["jp10y"][0] is not None and data["jp2y"][0] is not None:
        data["jp_yield_spread"] = data["jp10y"][0] - data["jp2y"][0]
    else:
        data["jp_yield_spread"] = None

    data["jp_rates_comment"] = generate_jp_rates_comment(data)

    # コモディティ
    data["gold"] = get_price_smart("GC=F", tv_symbol="TVC:GOLD")
    data["wti"] = get_price_smart("CL=F", tv_symbol="TVC:USOIL")
    data["copper"] = get_price_smart("HG=F", tv_symbol="TVC:HG1!")
    data["silver"] = get_price_smart("SI=F", tv_symbol="TVC:SILVER")
    data["natgas"] = get_price_smart("NG=F", tv_symbol="TVC:NATGAS")

    # 為替
    data["usd_jpy"], data["eur_jpy"], data["cny_jpy"] = get_fx()

    # 仮想通貨
    data["btc"] = get_price_smart("BTC-USD", tv_symbol="CRYPTO:BTCUSD")
    data["eth"] = get_eth()

    # 変化率（補助）
    data["nikkei_change"] = get_change(data["nikkei"])
    data["sp500_change"] = get_change(data["sp500"])
    data["wti_change"] = get_change(data["wti"])

    # スコア・コメント
    data["score"], data["raw_score"], data["raw_max"], data["judge"] = generate_score(data)
    data["comment"] = generate_comment(data)
    data["us_comment"] = generate_us_comment(data)
    data["fx_comment"] = generate_fx_comment(data)
    data["commodities_comment"] = generate_commodities_comment(data)
    data["rates_comment"] = generate_rates_comment(data)

    # 日本金利コメント（追加済）
    data["jp_rates_comment"] = generate_jp_rates_comment(data)

    # ニュース処理
    news_list = fetch_news()
    classified = classify_news_list(news_list)
    war_score, peace_score = score_news(classified)

    data["classified_news"] = classified
    data["war_score"] = war_score
    data["peace_score"] = peace_score

    return data

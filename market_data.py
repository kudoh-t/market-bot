import yfinance as yf
import requests
import pandas as pd
from datetime import datetime

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# ============================
# 汎用：Yahoo Finance 取得
# ============================
def get_yf_data(ticker):
    try:
        df = yf.download(ticker, period="5d", interval="1d", progress=False)
        if df.empty or len(df) < 2:
            return None, None

        close = df['Close'].iloc[:, 0] if isinstance(df['Close'], pd.DataFrame) else df['Close']
        last, prev = float(close.iloc[-1]), float(close.iloc[-2])
        return last, ((last - prev) / prev) * 100
    except:
        return None, None


# ============================
# FGI
# ============================
def get_fgi():
    try:
        url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
        res = requests.get(url, headers=headers, timeout=10)
        d = res.json()
        return int(d['fear_and_greed']['score']), int(d['fear_and_greed']['previous_close'])
    except:
        return None, None


# ============================
# VIX先物：Yahoo Finance（query1〜4）
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
        except:
            continue

    return None, None


# ============================
# VIX先物：FMP（無料API）
# ============================
def get_vix_futures_fmp():
    try:
        url = "https://financialmodelingprep.com/api/v3/quote/VX=F?apikey=demo"
        res = requests.get(url, timeout=5).json()
        last = res[0]["price"]
        prev = res[0]["previousClose"]
        return last, (last - prev) / prev * 100
    except:
        return None, None


# ============================
# VIX先物：推定（最終手段）
# ============================
def estimate_vix_futures(vix_price, vix_change):
    if vix_price is None or vix_change is None:
        return None, None
    # 価格は現物を流用、変化率は0.8倍
    return vix_price, vix_change * 0.8


# ============================
# VIX先物：フェイルオーバー統合
# ============================
def get_vix_futures_safe(vix_price, vix_change):
    # ① Yahoo Finance
    vxf = get_vix_futures_yahoo()
    if vxf[0] is not None:
        return vxf

    # ② FMP
    vxf = get_vix_futures_fmp()
    if vxf[0] is not None:
        return vxf

    # ③ 推定（VIX現物から）
    return estimate_vix_futures(vix_price, vix_change)


# ============================
# メイン：市場データ取得
# ============================
def get_market_data():
    data = {"date": datetime.now().strftime("%Y.%m.%d")}

    # FGI
    data["fgi"], data["fgi_prev"] = get_fgi()

    # 株価指数
    data["nq"], data["spx"], data["nky"] = (
        get_yf_data("NQ=F"),
        get_yf_data("ES=F"),
        get_yf_data("NIY=F")
    )

    # VIX現物
    data["vix"] = get_yf_data("^VIX")
    vix_price  = data["vix"][0] if data["vix"] else None
    vix_change = data["vix"][1] if data["vix"] else None

    # VIX先物（フェイルオーバー）
    data["vix_f"] = get_vix_futures_safe(vix_price, vix_change)

    # 金利
    data["us10y"], data["us2y"] = get_yf_data("^TNX"), get_yf_data("^IRX")

    # スプレッド
    if data["us10y"][0] is not None and data["us2y"][0] is not None:
        data["yield_spread"] = data["us10y"][0] - data["us2y"][0]
    else:
        data["yield_spread"] = None

    # コモディティ
    data["gold"], data["wti"], data["copper"] = (
        get_yf_data("GC=F"),
        get_yf_data("CL=F"),
        get_yf_data("HG=F")
    )

    # BTC
    data["btc"] = get_yf_data("BTC-USD")

    return data

import yfinance as yf
import requests
import pandas as pd
from datetime import datetime

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_yf_data(ticker, period="5d"):
    try:
        df = yf.download(ticker, period=period, interval="1d", progress=False)
        if df.empty or len(df) < 2:
            return None, None
        close_series = df['Close'].iloc[:, 0] if isinstance(df['Close'], pd.DataFrame) else df['Close']
        last_price = float(close_series.iloc[-1])
        prev_price = float(close_series.iloc[-2])
        change_pct = ((last_price - prev_price) / prev_price) * 100
        return last_price, change_pct
    except:
        return None, None

def get_fgi():
    try:
        url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
        res = requests.get(url, headers=headers, timeout=10)
        data = res.json()
        return int(data['fear_and_greed']['score']), int(data['fear_and_greed']['previous_close'])
    except:
        return None, None

def get_market_data():
    data = {"date": datetime.now().strftime("%Y.%m.%d")}
    data["fgi"], data["fgi_prev"] = get_fgi()
    data["nq"] = get_yf_data("NQ=F")
    data["spx"] = get_yf_data("ES=F")
    data["nky"] = get_yf_data("NIY=F")
    data["vix"] = get_yf_data("^VIX")
    data["vix_f"] = get_yf_data("VX=F")
    data["us10y"] = get_yf_data("^TNX")
    data["us2y"] = get_yf_data("^IRX")
    
    if data["us10y"][0] is not None and data["us2y"][0] is not None:
        data["yield_spread"] = data["us10y"][0] - data["us2y"][0]
    else:
        data["yield_spread"] = None

    data["gold"] = get_yf_data("GC=F")
    data["wti"] = get_yf_data("CL=F")
    data["copper"] = get_yf_data("HG=F")
    data["btc"] = get_yf_data("BTC-USD")
    return data
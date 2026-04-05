import yfinance as yf
import requests
import pandas as pd
from datetime import datetime

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

def get_yf_data(ticker):
    try:
        df = yf.download(ticker, period="5d", interval="1d", progress=False)
        if df.empty or len(df) < 2: return None, None
        close = df['Close'].iloc[:, 0] if isinstance(df['Close'], pd.DataFrame) else df['Close']
        last, prev = float(close.iloc[-1]), float(close.iloc[-2])
        return last, ((last - prev) / prev) * 100
    except: return None, None

def get_fgi():
    try:
        url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
        res = requests.get(url, headers=headers, timeout=10)
        d = res.json()
        return int(d['fear_and_greed']['score']), int(d['fear_and_greed']['previous_close'])
    except: return None, None

def get_market_data():
    data = {"date": datetime.now().strftime("%Y.%m.%d")}
    data["fgi"], data["fgi_prev"] = get_fgi()
    data["nq"], data["spx"], data["nky"] = get_yf_data("NQ=F"), get_yf_data("ES=F"), get_yf_data("NIY=F")
    data["vix"], data["vix_f"] = get_yf_data("^VIX"), get_yf_data("VX=F")
    data["us10y"], data["us2y"] = get_yf_data("^TNX"), get_yf_data("^IRX")
    data["yield_spread"] = (data["us10y"][0] - data["us2y"][0]) if (data["us10y"][0] and data["us2y"][0]) else None
    data["gold"], data["wti"], data["copper"] = get_yf_data("GC=F"), get_yf_data("CL=F"), get_yf_data("HG=F")
    data["btc"] = get_yf_data("BTC-USD")
    return data
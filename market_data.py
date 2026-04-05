import yfinance as yf
import requests
import pandas as pd
from datetime import datetime

# ============================
# 基本設定
# ============================
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# ============================
# Yahoo Financeデータ取得関数
# ============================
def get_yf_data(ticker, period="5d"):
    """
    (直近価格, 騰落率) のタプルを返す
    """
    try:
        df = yf.download(ticker, period=period, interval="1d", progress=False)
        if df.empty or len(df) < 2:
            return None, None
        
        # 終値系列を取得（DataFrameでもSeriesでも対応できるように）
        if 'Close' in df.columns:
            close_series = df['Close']
            if isinstance(close_series, pd.DataFrame):
                close_series = close_series.iloc[:, 0]
        else:
            return None, None
            
        last_price = float(close_series.iloc[-1])
        prev_price = float(close_series.iloc[-2])
        change_pct = ((last_price - prev_price) / prev_price) * 100
        
        return last_price, change_pct
    except Exception as e:
        print(f"yfinance取得エラー ({ticker}): {e}")
        return None, None

# ============================
# Fear & Greed Index 取得関数（API方式）
# ============================
def get_fgi():
    """
    CNNの内部APIから現在のスコアと前日終値を直接取得
    """
    try:
        # WebスクレイピングではなくAPIを叩くことで安定化
        url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        data = res.json()
        
        current_score = int(data['fear_and_greed']['score'])
        previous_close = int(data['fear_and_greed']['previous_close'])
        
        return current_score, previous_close
    except Exception as e:
        print(f"FGI API取得エラー: {e}")
        return None, None

# ============================
# メイン：市場データ一括取得
# ============================
def get_market_data():
    print("=== get_market_data start ===")
    data = {}
    
    # 取得日時
    data["date"] = datetime.now().strftime("%Y.%m.%d")

    # 1. 投資家心理 (FGI)
    fgi_now, fgi_prev = get_fgi()
    data["fgi"] = fgi_now
    data["fgi_prev"] = fgi_prev

    # 2. 主要指数
    data["nq"] = get_yf_data("NQ=F")    # ナスダック100先物
    data["spx"] = get_yf_data("ES=F")   # S&P500先物
    data["nky"] = get_yf_data("NIY=F")  # 日経平均先物

    # 3. リスク指標 (VIX)
    data["vix"] = get_yf_data("^VIX")   # VIX現物
    data["vix_f"] = get_yf_data("VX=F") # VIX先物

    # 4. 金利
    data["us10y"] = get_yf_data("^TNX") # 米10年債
    data["us2y"] = get_yf_data("^IRX")  # 米2年債（13週短期国債利回り等で代用）
    
    # 利回り差計算
    if data["us10y"][0] is not None and data["us2y"][0] is not None:
        data["yield_spread"] = data["us10y"][0] - data["us2y"][0]
    else:
        data["yield_spread"] = None

    # 5. 商品
    data["gold"] = get_yf_data("GC=F")   # 金
    data["wti"] = get_yf_data("CL=F")    # 原油
    data["copper"] = get_yf_data("HG=F") # 銅

    # 6. 仮想通貨
    data["btc"] = get_yf_data("BTC-USD")

    print("=== get_market_data end ===")
    return data
import requests
from bs4 import BeautifulSoup
import datetime
import yfinance as yf

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# -----------------------------
# 1. Fear & Greed Index (CNN)
# -----------------------------
def get_fgi():
    try:
        url = "https://www.cnn.com/markets/fear-and-greed"
        res = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")
        
        score_tag = soup.find("span", {"class": "market-fng-gauge__dial-number-value"})
        if score_tag:
            val = score_tag.text.strip()
            return int(val), None
        return None, None
    except Exception as e:
        print(f"FGI取得エラー: {e}")
        return None, None

# -----------------------------
# 2-6. 汎用データ取得 (Yahoo Finance)
# -----------------------------
def get_yf_data(ticker):
    """Yahoo Financeから価格と前日比(%)を取得（休日対応版）"""
    try:
        symbol = yf.Ticker(ticker)
        # 休日を考慮して直近5日分を取得
        hist = symbol.history(period="5d")
        
        if hist.empty or len(hist) < 1:
            return None, None
        
        current_price = hist['Close'].iloc[-1]
        
        if len(hist) >= 2:
            prev_close = hist['Close'].iloc[-2]
            change_pct = ((current_price - prev_close) / prev_close) * 100
        else:
            change_pct = 0.0
        
        return round(current_price, 2), round(change_pct, 2)
    except Exception as e:
        print(f"Ticker {ticker} 取得エラー: {e}")
        return None, None

# -----------------------------
# 7. ニュース（Yahoo Topics）
# -----------------------------
def get_news():
    try:
        url = "https://news.yahoo.co.jp/topics/top-picks"
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")

        news_list = []
        topics = soup.select("li a")
        for t in topics:
            title = t.text.replace("写真", "").strip()
            if title and len(news_list) < 10:
                news_list.append(title)
        return news_list
    except Exception as e:
        print(f"ニュース取得エラー: {e}")
        return []

# -----------------------------
# ★ メイン：データをまとめて取得
# -----------------------------
def get_market_data():
    print("=== get_market_data start ===")

    data = {
        "date": datetime.datetime.now().strftime("%Y.%m.%d"),
        "fgi": None,
        "nq": None,      # Nasdaq 100 (^NDX)
        "spx": None,     # S&P 500 (^GSPC)
        "nky": None,     # 日経225 (^N225)
        "vix": None,     # VIX指数 (^VIX)
        "us10y": None,   # 米10年債利回り (^TNX)
        "us2y": None,    # 米13週物利回り (^IRX) ※短期代用
        "yield_spread": None,
        "gold": None,    # 金先物 (GC=F)
        "wti": None,     # 原油先物 (CL=F)
        "copper": None,  # 銅先物 (HG=F) ★追加
        "btc": None,     # BTC/USD (BTC-USD)
        "news": [],
    }

    # 1. FGI
    data["fgi"], _ = get_fgi()

    # 2. 指数
    data["nq"] = get_yf_data("^NDX")
    data["spx"] = get_yf_data("^GSPC")
    data["nky"] = get_yf_data("^N225")

    # 3. VIX
    data["vix"] = get_yf_data("^VIX")

    # 4. 金利
    data["us10y"] = get_yf_data("^TNX")
    data["us2y"] = get_yf_data("^IRX")
    if data["us10y"] and data["us2y"] and data["us10y"][0] is not None and data["us2y"][0] is not None:
        data["yield_spread"] = round(data["us10y"][0] - data["us2y"][0], 3)

    # 5. コモディティ
    data["gold"] = get_yf_data("GC=F")
    data["wti"] = get_yf_data("CL=F")
    data["copper"] = get_yf_data("HG=F") # ★銅を追加

    # 6. BTC
    data["btc"] = get_yf_data("BTC-USD")

    # 7. ニュース
    data["news"] = get_news()

    print("=== get_market_data end ===")
    return data

if __name__ == "__main__":
    import pprint
    pprint.pprint(get_market_data())
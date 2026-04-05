import requests
from bs4 import BeautifulSoup
import datetime
import yfinance as yf

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

# -----------------------------
# 1. Fear & Greed Index (CNN)
# -----------------------------
def get_fgi():
    """CNNのサイトからF&G Indexを取得（構造変更に弱いため注意）"""
    try:
        url = "https://www.cnn.com/markets/fear-and-greed"
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        
        # 最新のCNNのクラス名や構造に合わせて取得
        # ※CNNは頻繁に構造が変わるため、取得できない場合はNoneを返す
        score_tag = soup.find("span", {"class": "market-fng-gauge__dial-number-value"})
        if score_tag:
            return int(score_tag.text), None
        return None, None
    except Exception as e:
        print(f"FGI取得エラー: {e}")
        return None, None

# -----------------------------
# 2-6. 汎用データ取得 (Yahoo Finance)
# -----------------------------
def get_yf_data(ticker):
    """Yahoo Financeから価格と前日比(%)を取得"""
    try:
        data = yf.Ticker(ticker)
        # fast_info または historyを使用して最新値を取得
        hist = data.history(period="2d")
        if len(hist) < 2:
            # 休日などでデータが足りない場合は直近1日分
            price = hist['Close'].iloc[-1]
            return round(price, 2), 0.0
        
        prev_close = hist['Close'].iloc[-2]
        current_price = hist['Close'].iloc[-1]
        change_pct = ((current_price - prev_close) / prev_close) * 100
        
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

        # クラス名は変わることがあるため、aタグの構造から取得
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
def get_all_market_data():
    print("=== get_all_market_data start ===")

    data = {
        "date": datetime.datetime.now().strftime("%Y.%m.%d"),
        "fgi": None,
        "nq": None,      # Nasdaq 100
        "spx": None,     # S&P 500
        "nky": None,     # Nikkei 225
        "vix": None,
        "us10y": None,   # 米10年債
        "us2y": None,    # 米2年債
        "yield_spread": None,
        "gold": None,
        "wti": None,     # 原油
        "btc": None,
        "news": [],
    }

    # 1. FGI
    data["fgi"], _ = get_fgi()

    # 2. 指数 (Yahoo Financeのティッカーを使用)
    data["nq"] = get_yf_data("^NDX")
    data["spx"] = get_yf_data("^GSPC")
    data["nky"] = get_yf_data("^N225")

    # 3. VIX
    data["vix"] = get_yf_data Ripley"^VIX")

    # 4. 金利
    data["us10y"] = get_yf_data("^TNX") # 10-Year Treasury Yield
    data["us2y"] = get_yf_data("^IRX")  # 13-week T-Bill (2年債は^TYX(30y)等と比較して適切なものを選んでください)
    
    # 利回り差の計算
    if data["us10y"][0] and data["us2y"][0]:
        data["yield_spread"] = round(data["us10y"][0] - data["us2y"][0], 3)

    # 5. コモディティ
    data["gold"] = get_yf_data("GC=F")
    data["wti"] = get_yf_data("CL=F")

    # 6. BTC
    data["btc"] = get_yf_data("BTC-USD")

    # 7. ニュース
    data["news"] = get_news()

    print("=== get_all_market_data end ===")
    return data

if __name__ == "__main__":
    result = get_all_market_data()
    import pprint
    pprint.pprint(result)
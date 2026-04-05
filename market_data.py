import requests
from bs4 import BeautifulSoup
import datetime
import yfinance as yf
import re

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# -----------------------------
# 1. Fear & Greed Index (CNN) - 取得を試みるが失敗しても無視する
# -----------------------------
def get_fgi():
    try:
        url = "https://www.cnn.com/markets/fear-and-greed"
        res = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")
        
        score_tag = soup.find("span", {"class": "market-fng-gauge__dial-number-value"})
        if score_tag and score_tag.text.strip().isdigit():
            return int(score_tag.text.strip()), None
        
        # 予備：テキストから数字を探す
        match = re.search(r'"score":(\d+)', res.text)
        if match:
            return int(match.group(1)), None
            
        return None, None
    except Exception as e:
        print(f"FGI取得スキップ（取得不可）: {e}")
        return None, None

# -----------------------------
# 2-6. 汎用データ取得 (Yahoo Finance)
# -----------------------------
def get_yf_data(ticker):
    try:
        symbol = yf.Ticker(ticker)
        # 5日分取得して確実に最新データを確保
        hist = symbol.history(period="5d")
        
        if hist.empty or len(hist) < 1:
            print(f"Warning: {ticker} のデータが空です")
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
    except Exception:
        return []

# -----------------------------
# ★ メイン：エラーが起きても辞書を最後まで完成させる
# -----------------------------
def get_market_data():
    print("=== get_market_data start ===")
    
    # 全項目をNoneで初期化しておく
    data = {
        "date": datetime.datetime.now().strftime("%Y.%m.%d"),
        "fgi": None, "fgi_prev": None,
        "nq": (None, None), "spx": (None, None), "nky": (None, None),
        "vix": (None, None),
        "us10y": (None, None), "us2y": (None, None), "yield_spread": None,
        "gold": (None, None), "wti": (None, None), "copper": (None, None),
        "btc": (None, None),
        "news": []
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
    if data["us10y"][0] and data["us2y"][0]:
        data["yield_spread"] = round(data["us10y"][0] - data["us2y"][0], 3)

    # 5. コモディティ
    data["gold"] = get_yf_data("GC=F")
    data["wti"] = get_yf_data("CL=F")
    data["copper"] = get_yf_data("HG=F")

    # 6. BTC
    data["btc"] = get_yf_data("BTC-USD")

    # 7. ニュース
    data["news"] = get_news()

    print("=== get_market_data end ===")
    return data
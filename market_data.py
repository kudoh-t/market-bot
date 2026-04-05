import requests
from bs4 import BeautifulSoup
import datetime
import json

headers = {"User-Agent": "Mozilla/5.0"}

# -----------------------------
# 1. Fear & Greed Index (CNN)
# -----------------------------
def get_fgi():
    try:
        url = "https://money.cnn.com/data/fear-and-greed/"
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")

        score = soup.find("div", {"id": "needleChart"}).get("data-fng-index")
        prev = soup.find("div", {"id": "needleChart"}).get("data-fng-previous")

        return int(score), int(prev)
    except:
        return None, None


# -----------------------------
# 2. 指数（Investing.com）
# -----------------------------
def investing_get(pair_id):
    try:
        url = f"https://api.investing.com/api/financialdata/{pair_id}/historical/chart/"
        res = requests.get(url, headers=headers, timeout=10)
        js = res.json()

        price = js["data"][-1]["last_close"]
        change = js["data"][-1]["change_percent"]

        return price, change
    except:
        return None, None


# -----------------------------
# 3. CNBC 汎用取得（VIX・金利）
# -----------------------------
def cnbc_get(url):
    try:
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")

        price_tag = soup.find("span", {"class": "QuoteStrip-lastPrice"})
        if not price_tag:
            return None, None
        price = float(price_tag.text.replace(",", "").replace("$", ""))

        change_tag = (
            soup.find("span", {"class": "QuoteStrip-changePct"}) or
            soup.find("span", {"data-field": "changePct"}) or
            soup.find("span", {"class": "QuoteStrip-change"}) or
            soup.find("span", {"data-field": "change"})
        )

        if not change_tag:
            return price, 0.0

        change_text = change_tag.text.replace("%", "").replace("+", "").replace("−", "-")
        change_percent = float(change_text)

        return price, change_percent
    except:
        return None, None


# -----------------------------
# 4. TradingView 汎用取得（Gold, WTI, Copper, BTC）
# -----------------------------
def tv_get(symbol):
    try:
        url = f"https://api.tradingview.com/symbols/{symbol}/"
        res = requests.get(url, headers=headers, timeout=10)
        js = res.json()

        price = js["lp"]
        change = js["chp"]
        return price, change
    except:
        return None, None


# -----------------------------
# 7. ニュース（Yahooカテゴリ別）
# -----------------------------
def get_news():
    try:
        url = "https://news.yahoo.co.jp/topics"
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")

        topics = soup.find_all("a", {"class": "sc-dRFtgE"})
        news_list = []

        for t in topics[:10]:
            title = t.text.strip()
            news_list.append(title)

        return news_list
    except:
        return []


# -----------------------------
# ★ メイン：1〜7 をまとめて取得
# -----------------------------
def get_all_market_data():
    print("=== get_all_market_data start ===")

    data = {
        "date": datetime.datetime.now().strftime("%Y.%m.%d"),

        # 1. FGI
        "fgi": None,
        "fgi_prev": None,

        # 2. 指数
        "nq": None,
        "spx": None,
        "nky": None,

        # 3. VIX
        "vix": None,
        "vix_f": None,

        # 4. 金利
        "us10y": None,
        "us2y": None,
        "yield_spread": None,

        # 5. コモディティ
        "gold": None,
        "wti": None,
        "copper": None,

        # 6. BTC
        "btc": None,

        # 7. ニュース
        "news": [],
    }

    # --- 1. FGI ---
    data["fgi"], data["fgi_prev"] = get_fgi()

    # --- 2. 指数（Investing.com pair_id） ---
    data["nq"] = investing_get(8874)     # NASDAQ100
    data["spx"] = investing_get(166)     # S&P500
    data["nky"] = investing_get(178)     # Nikkei225

    # --- 3. VIX ---
    data["vix"] = cnbc_get("https://www.cnbc.com/quotes/.VIX")
    data["vix_f"] = cnbc_get("https://www.cnbc.com/quotes/VIX3M")

    # --- 4. 金利 ---
    data["us10y"] = cnbc_get("https://www.cnbc.com/quotes/US10Y")
    data["us2y"] = cnbc_get("https://www.cnbc.com/quotes/US2Y")

    # 利回り差
    try:
        if data["us10y"][0] is not None and data["us2y"][0] is not None:
            data["yield_spread"] = round(data["us10y"][0] - data["us2y"][0], 3)
    except:
        data["yield_spread"] = None

    # --- 5. コモディティ ---
    data["gold"] = tv_get("GOLD")
    data["wti"] = tv_get("USOIL")
    data["copper"] = tv_get("COPPER")

    # --- 6. BTC ---
    data["btc"] = tv_get("BTCUSD")

    # --- 7. ニュース ---
    data["news"] = get_news()

    print("=== get_all_market_data end ===")
    return data

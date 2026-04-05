import requests
from bs4 import BeautifulSoup
import datetime

# ============================
# 汎用スクレイピング関数（CNBC）
# ============================

def cnbc_get(url):
    """
    CNBC の銘柄ページから現在値と変化率を取得
    """
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=8)
        soup = BeautifulSoup(res.text, "html.parser")

        price_tag = soup.find("span", {"class": "QuoteStrip-lastPrice"})
        change_tag = soup.find("span", {"class": "QuoteStrip-changePct"})

        if not price_tag or not change_tag:
            return None, None

        price = float(price_tag.text.replace(",", "").replace("$", ""))
        change_percent = float(change_tag.text.replace("%", "").replace("+", "").replace("−", "-"))

        return price, change_percent

    except:
        return None, None


# ============================
# Yahoo Finance（BTC）
# ============================

def yahoo_btc():
    try:
        url = "https://finance.yahoo.com/quote/BTC-USD/"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=8)
        soup = BeautifulSoup(res.text, "html.parser")

        price_tag = soup.find("fin-streamer", {"data-field": "regularMarketPrice"})
        change_tag = soup.find("fin-streamer", {"data-field": "regularMarketChangePercent"})

        if not price_tag or not change_tag:
            return None, None

        price = float(price_tag.text.replace(",", ""))
        change_percent = float(change_tag.text.replace("%", "").replace("+", "").replace("−", "-"))

        return price, change_percent

    except:
        return None, None


# ============================
# FGI（CNN API）
# ============================

def get_fgi():
    try:
        url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
        res = requests.get(url, timeout=5).json()
        now = res["fear_and_greed"]["score"]
        prev = res["fear_and_greed"]["previous_close"]
        return now, prev
    except:
        return None, None


# ============================
# まとめて取得
# ============================

def get_market_data():
    fgi_now, fgi_prev = get_fgi()

    # CNBC URL 一覧
    urls = {
        "vix": "https://www.cnbc.com/quotes/.VIX",
        "vxf": "https://www.cnbc.com/quotes/VX1",
        "nq": "https://www.cnbc.com/quotes/NQ=F",
        "es": "https://www.cnbc.com/quotes/ES=F",
        "nk": "https://www.cnbc.com/quotes/NK=F",
        "gold": "https://www.cnbc.com/quotes/GC=F",
        "wti": "https://www.cnbc.com/quotes/CL=F",
        "cop": "https://www.cnbc.com/quotes/HG=F",
        "u10": "https://www.cnbc.com/quotes/US10Y",
        "u2": "https://www.cnbc.com/quotes/US2Y",
    }

    # CNBC から取得
    vix_p, vix_c = cnbc_get(urls["vix"])
    vxf_p, vxf_c = cnbc_get(urls["vxf"])
    nq_p, nq_c = cnbc_get(urls["nq"])
    es_p, es_c = cnbc_get(urls["es"])
    nk_p, nk_c = cnbc_get(urls["nk"])
    gold_p, gold_c = cnbc_get(urls["gold"])
    wti_p, wti_c = cnbc_get(urls["wti"])
    cop_p, cop_c = cnbc_get(urls["cop"])
    u10_p, u10_c = cnbc_get(urls["u10"])
    u2_p, u2_c = cnbc_get(urls["u2"])

    spread = None
    if u10_p is not None and u2_p is not None:
        spread = u10_p - u2_p

    # BTC（Yahoo）
    btc_p, btc_c = yahoo_btc()

    return {
        "date": datetime.datetime.now().strftime("%Y.%m.%d"),
        "fgi_score": fgi_now,
        "fgi_prev": fgi_prev,
        "vix_p": vix_p,
        "vix_c": vix_c,
        "vxf_p": vxf_p,
        "vxf_c": vxf_c,
        "u10_p": u10_p,
        "u10_c": u10_c,
        "u2_p": u2_p,
        "u2_c": u2_c,
        "spread": spread,
        "gold_p": gold_p,
        "gold_c": gold_c,
        "wti_p": wti_p,
        "wti_c": wti_c,
        "cop_p": cop_p,
        "cop_c": cop_c,
        "nq_p": nq_p,
        "nq_c": nq_c,
        "es_p": es_p,
        "es_c": es_c,
        "nk_p": nk_p,
        "nk_c": nk_c,
        "btc_p": btc_p,
        "btc_c": btc_c,
    }
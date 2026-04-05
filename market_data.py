import requests
import datetime

# ============================
# FGI（Fear & Greed Index）
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
# VIX（現物・先物）
# ============================

def get_vix():
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX"
        res = requests.get(url, timeout=5).json()
        price = res["chart"]["result"][0]["meta"]["regularMarketPrice"]
        change = res["chart"]["result"][0]["meta"]["regularMarketChangePercent"]
        return price, change
    except:
        return None, None


def get_vix_future():
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX"
        res = requests.get(url, timeout=5).json()
        price = res["chart"]["result"][0]["meta"]["regularMarketPrice"]
        change = res["chart"]["result"][0]["meta"]["regularMarketChangePercent"]
        return price, change
    except:
        return None, None


# ============================
# 金利（2年・10年）
# ============================

def get_yield(symbol):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        res = requests.get(url, timeout=5).json()
        price = res["chart"]["result"][0]["meta"]["regularMarketPrice"]
        change = res["chart"]["result"][0]["meta"]["regularMarketChangePercent"]
        return price, change
    except:
        return None, None


# ============================
# BTC
# ============================

def get_btc():
    try:
        url = "https://api.coindesk.com/v1/bpi/currentprice/USD.json"
        res = requests.get(url, timeout=5).json()
        price = float(res["bpi"]["USD"]["rate"].replace(",", ""))
        return price
    except:
        return None


# ============================
# コモディティ（WTI, Gold, Copper）
# ============================

def get_yahoo_price(symbol):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        res = requests.get(url, timeout=5).json()
        price = res["chart"]["result"][0]["meta"]["regularMarketPrice"]
        change = res["chart"]["result"][0]["meta"]["regularMarketChangePercent"]
        return price, change
    except:
        return None, None


# ============================
# 株価指数先物（NQ, ES, NK）
# ============================

def get_index(symbol):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        res = requests.get(url, timeout=5).json()
        price = res["chart"]["result"][0]["meta"]["regularMarketPrice"]
        change = res["chart"]["result"][0]["meta"]["regularMarketChangePercent"]
        return price, change
    except:
        return None, None


# ============================
# まとめて取得
# ============================

def get_market_data():
    fgi_now, fgi_prev = get_fgi()

    vix_p, vix_c = get_vix()
    vxf_p, vxf_c = get_vix_future()

    u10_p, u10_c = get_yield("^TNX")
    u2_p, u2_c = get_yield("^IRX")

    spread = None
    if u10_p is not None and u2_p is not None:
        spread = (u10_p / 100) - (u2_p / 100)

    gold_p, gold_c = get_yahoo_price("GC=F")
    wti_p, wti_c = get_yahoo_price("CL=F")
    cop_p, cop_c = get_yahoo_price("HG=F")

    nq_p, nq_c = get_index("NQ=F")
    es_p, es_c = get_index("ES=F")
    nk_p, nk_c = get_index("NK=F")

    btc_p = get_btc()
    btc_c = 0  # 変化率は省略（必要なら追加）

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


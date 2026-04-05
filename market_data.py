import requests
import datetime

# ============================
# TradingView 汎用取得関数
# ============================

def tv_get(symbol):
    """
    TradingView から close / change / change_percent を取得
    """
    try:
        url = "https://scanner.tradingview.com/america/scan"
        payload = {
            "symbols": {
                "tickers": [symbol],
                "query": {"types": []}
            },
            "columns": ["close", "change", "change_percent"]
        }
        res = requests.post(url, json=payload, timeout=5).json()
        d = res["data"][0]["d"]
        price = d[0]
        change = d[2]  # change_percent
        return price, change
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
# BTC（TradingView）
# ============================

def get_btc():
    return tv_get("BINANCE:BTCUSDT")

# ============================
# まとめて取得
# ============================

def get_market_data():
    fgi_now, fgi_prev = get_fgi()

    # VIX（現物・先物）
    vix_p, vix_c = tv_get("CBOE:VIX")
    vxf_p, vxf_c = tv_get("CBOE:VIX1!")

    # 金利
    u10_p, u10_c = tv_get("TVC:US10Y")
    u2_p, u2_c = tv_get("TVC:US02Y")

    spread = None
    if u10_p is not None and u2_p is not None:
        spread = (u10_p - u2_p)

    # コモディティ
    gold_p, gold_c = tv_get("COMEX:GC1!")
    wti_p, wti_c = tv_get("NYMEX:CL1!")
    cop_p, cop_c = tv_get("COMEX:HG1!")

    # 株価指数先物
    nq_p, nq_c = tv_get("CME_MINI:NQ1!")
    es_p, es_c = tv_get("CME_MINI:ES1!")
    nk_p, nk_c = tv_get("OSE:NK2251!")

    # BTC
    btc_p, btc_c = get_btc()

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
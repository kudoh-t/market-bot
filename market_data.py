import requests
import datetime

# ============================
# Investing.com 汎用取得関数
# ============================

def inv_get(id):
    """
    Investing.com の非公式APIから価格と変化率を取得
    """
    try:
        url = f"https://api.investing.com/api/financialdata/{id}/historical/chart/?interval=P1D&pointscount=2"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json"
        }
        res = requests.get(url, headers=headers, timeout=5).json()

        data = res["data"]
        if len(data) < 2:
            return None, None

        prev = data[-2]["last_close"]
        price = data[-1]["last_close"]

        if prev is None or price is None:
            return None, None

        change_percent = (price - prev) / prev * 100
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

    # VIX（現物・先物）
    vix_p, vix_c = inv_get(44336)
    vxf_p, vxf_c = inv_get(44337)

    # 金利
    u10_p, u10_c = inv_get(23705)
    u2_p, u2_c = inv_get(23701)

    spread = None
    if u10_p is not None and u2_p is not None:
        spread = (u10_p - u2_p)

    # コモディティ
    gold_p, gold_c = inv_get(8830)
    wti_p, wti_c = inv_get(8849)
    cop_p, cop_c = inv_get(8836)

    # 株価指数先物
    nq_p, nq_c = inv_get(8874)
    es_p, es_c = inv_get(8839)
    nk_p, nk_c = inv_get(178)

    # BTC（Investing.com）
    btc_p, btc_c = inv_get(945629)

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
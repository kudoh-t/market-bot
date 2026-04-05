import requests
from bs4 import BeautifulSoup
import datetime

def cnbc_get(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")

        # --- 価格 ---
        price_tag = soup.find("span", {"class": "QuoteStrip-lastPrice"})
        if not price_tag:
            return None, None
        price = float(price_tag.text.replace(",", "").replace("$", ""))

        # --- 変化率（複数パターン対応） ---
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

    except Exception as e:
        print("[cnbc_get] error:", e)
        return None, None


def get_market_data():
    print("=== get_market_data start ===")

    vix_url = "https://www.cnbc.com/quotes/.VIX"
    vix_p, vix_c = cnbc_get(vix_url)

    print("VIX:", vix_p, vix_c)

    return {
        "date": datetime.datetime.now().strftime("%Y.%m.%d"),
        "vix_p": vix_p,
        "vix_c": vix_c,
    }
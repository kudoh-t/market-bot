import requests
from bs4 import BeautifulSoup
import datetime

def cnbc_get(url):
    try:
        print(f"[cnbc_get] url={url}")
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=10)
        print(f"[cnbc_get] status={res.status_code}")

        soup = BeautifulSoup(res.text, "html.parser")

        price_tag = soup.find("span", {"class": "QuoteStrip-lastPrice"})
        change_tag = soup.find("span", {"class": "QuoteStrip-changePct"})

        print("[cnbc_get] price_tag:", price_tag)
        print("[cnbc_get] change_tag:", change_tag)

        if not price_tag or not change_tag:
            return None, None

        price = float(price_tag.text.replace(",", "").replace("$", ""))
        change_percent = float(change_tag.text.replace("%", "").replace("+", "").replace("−", "-"))

        return price, change_percent

    except Exception as e:
        print("[cnbc_get] error:", e)
        return None, None


def get_market_data():
    print("=== get_market_data start ===")

    # VIX（現物）
    vix_url = "https://www.cnbc.com/quotes/.VIX"
    vix_p, vix_c = cnbc_get(vix_url)

    print("VIX:", vix_p, vix_c)

    return {
        "date": datetime.datetime.now().strftime("%Y.%m.%d"),
        "vix_p": vix_p,
        "vix_c": vix_c,
    }
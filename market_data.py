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
            return price, 0.0  # 変化率が取れない場合は 0 とする

        change_text = change_tag.text.replace("%", "").replace("+", "").replace("−", "-")
        change_percent = float(change_text)

        return price, change_percent

    except Exception as e:
        print("[cnbc_get] error:", e)
        return None, None
import os
import json
import logging

def fetch_vix_futures():
    """
    VIX先物データを複数のソースから取得し、現在値と前日比(%)を返す。
    成功した場合はキャッシュを更新する。
    """
    CACHE_FILE = "vixf_cache.json"
    
    # 試行する取得ロジックのリスト
    sources = []

    # 1. Yahoo Finance API (v7/v8)
    def try_yahoo():
        # クエリパラメータに user-agent 等が必要な場合があるため注意
        url = "https://query1.finance.yahoo.com/v8/finance/chart/VX=F"
        data = get_json(url)
        result = data["chart"]["result"][0]
        price = result["meta"].get("regularMarketPrice")
        prev = result["meta"].get("chartPreviousClose")
        if price and prev:
            return float(price), float((price - prev) / prev * 100)
        return None
    sources.append(try_yahoo)

    # 2. MarketWatch (HTML Scraping)
    def try_marketwatch():
        url = "https://www.marketwatch.com/investing/future/vx00"
        soup = get_soup(url)
        # セレクタは時期により変わる可能性があるため、より汎用的なものを指定
        price_text = soup.select_one("bg-quote[field='last']").text if soup.select_one("bg-quote[field='last']") else soup.select_one(".intraday__price .value").text
        change_text = soup.select_one("bg-quote[field='percentChange']").text if soup.select_one("bg-quote[field='percentChange']") else soup.select_one(".change--percent--q .value").text
        
        price = float(price_text.replace(",", "").strip())
        change = float(change_text.replace("%", "").replace("+", "").strip())
        return price, change
    sources.append(try_marketwatch)

    # 3. Financial Modeling Prep (API)
    def try_fmp():
        api_key = os.getenv("FMP_API_KEY")
        if not api_key: return None
        url = f"https://financialmodelingprep.com/api/v3/quote/VX=F?apikey={api_key}"
        data = get_json(url)
        if data:
            item = data[0]
            return float(item.get("price")), float(item.get("changesPercentage"))
        return None
    sources.append(try_fmp)

    # --- 実行セクション ---
    for fetch_func in sources:
        try:
            result = fetch_func()
            if result:
                price, change = result
                # 成功したらキャッシュを更新
                with open(CACHE_FILE, "w") as f:
                    json.dump({"price": price, "change": change}, f)
                return price, change
        except Exception as e:
            logging.error(f"{fetch_func.__name__} failed: {e}")
            continue

    # --- 全ソース失敗時のキャッシュ復旧 ---
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r") as f:
                cache = json.load(f)
                logging.info("Returned data from cache.")
                return cache["price"], cache["change"]
    except Exception as e:
        logging.error(f"Cache recovery failed: {e}")

    return 0.0, 0.0
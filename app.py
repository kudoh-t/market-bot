import requests
import json
import os
import logging
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

# ============================
# 設定：環境変数
# ============================
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")
FMP_API_KEY = os.getenv("FMP_API_KEY")

CACHE_FILE = "vixf_cache.json"

# ============================
# LINE Messaging API
# ============================
def send_line(text: str):
    if not LINE_ACCESS_TOKEN or not LINE_USER_ID:
        print("LINE設定が不足しています。")
        return
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_ACCESS_TOKEN}",
    }
    body = {
        "to": LINE_USER_ID,
        "messages": [{"type": "text", "text": text}],
    }
    try:
        response = requests.post(url, headers=headers, data=json.dumps(body), timeout=10)
        if response.status_code == 200:
            print("LINE送信成功")
        else:
            print(f"LINE送信失敗: {response.status_code} {response.text}")
    except Exception as e:
        print(f"LINE通信エラー: {e}")

# ============================
# 共通ヘルパー関数
# ============================
def get_json(url: str):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    return requests.get(url, headers=headers, timeout=15).json()

def get_soup(url: str):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    resp = requests.get(url, headers=headers, timeout=15)
    return BeautifulSoup(resp.text, "html.parser")

def get_data_date(meta):
    ts = meta.get("regularMarketTime")
    if ts:
        dt = datetime.fromtimestamp(ts, timezone.utc) + timedelta(hours=9)
        return dt.strftime("%Y.%m.%d")
    return "不明"

# ============================
# VIX先物：取得ロジック（三重化＋キャッシュ）
# ============================
def fetch_vix_futures():
    """VIX先物を複数ソースから試行取得し、成功時にキャッシュ保存、失敗時にキャッシュ復旧を行う"""
    
    # 1. Yahoo Finance API (v8)
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/VX=F"
        data = get_json(url)
        res = data["chart"]["result"][0]
        p = float(res["meta"]["regularMarketPrice"])
        prev = float(res["meta"]["chartPreviousClose"])
        c = (p - prev) / prev * 100
        _save_vxf_cache(p, c)
        return p, c
    except: pass

    # 2. MarketWatch HTML
    try:
        url = "https://www.marketwatch.com/investing/future/vx00"
        soup = get_soup(url)
        p_el = soup.select_one("bg-quote[field='last']") or soup.select_one(".intraday__price .value")
        c_el = soup.select_one("bg-quote[field='percentChange']") or soup.select_one(".change--percent--q .value")
        if p_el and c_el:
            p = float(p_el.text.replace(",", "").strip())
            c = float(c_el.text.replace("%", "").replace("+", "").strip())
            _save_vxf_cache(p, c)
            return p, c
    except: pass

    # 3. FMP API (Option)
    if FMP_API_KEY:
        try:
            url = f"https://financialmodelingprep.com/api/v3/quote/VX=F?apikey={FMP_API_KEY}"
            data = get_json(url)
            if data:
                p, c = float(data[0]["price"]), float(data[0]["changesPercentage"])
                _save_vxf_cache(p, c)
                return p, c
        except: pass

    # 4. キャッシュ復旧
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r") as f:
                cache = json.load(f)
                return cache["price"], cache["change"]
    except: pass

    return 0.0, 0.0

def _save_vxf_cache(price, change):
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump({"price": price, "change": change, "time": datetime.now().isoformat()}, f)
    except: pass

# ============================
# 市場データ集約
# ============================
def get_market_data():
    d = {"data_date": "不明"}

    # Yahoo系の一括取得（エラー耐性あり）
    targets = {
        "gold": "GC=F", "wti": "CL=F", "vix": "%5EVIX", 
        "nq": "NQ=F", "nk": "NK=F", "es": "ES=F", 
        "us10y": "%5ETNX", "us2y": "%5EIRX", "btc": "BTC-USD"
    }

    for key, symbol in targets.items():
        try:
            raw = get_json(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}")
            meta = raw["chart"]["result"][0]["meta"]
            p = meta["regularMarketPrice"]
            prev = meta["chartPreviousClose"]
            d[f"{key}_price"] = p
            d[f"{key}_change"] = (p - prev) / prev * 100
            if key == "vix": d["data_date"] = get_data_date(meta)
        except:
            d[f"{key}_price"], d[f"{key}_change"] = 0.0, 0.0

    # USD/JPY (外部API)
    try:
        fx = get_json("https://api.frankfurter.app/latest?from=USD&to=JPY")
        d["usd_jpy"] = fx["rates"]["JPY"]
    except: d["usd_jpy"] = 0.0

    # VIX先物 (刷新した統合関数)
    d["vxf_price"], d["vxf_change"] = fetch_vix_futures()

    # イールドカーブ
    d["yield_spread"] = d["us10y_price"] - d["us2y_price"] if d["us2y_price"] != 0 else 0.0

    return d

# ============================
# ロジック・メッセージ (統合)
# ============================
def detect_mode(vix_price):
    if vix_price >= 20: return "war"
    if 0 < vix_price <= 15: return "peace"
    return "transition"

def scale_score(score, max_s):
    return min(max(int(score / max_s * 100), 0), 100)

def classify_zone(scaled, mode):
    if mode == "war":
        if scaled >= 80: return "反転確定ゾーン"
        if scaled >= 60: return "反転の可能性大"
        if scaled >= 40: return "反転の初期兆候"
        return "有事継続"
    else:
        if scaled >= 80: return "強い上昇トレンド"
        if scaled >= 60: return "上昇バイアスあり"
        if scaled >= 40: return "上昇の初期"
        return "トレンド不明瞭"

def calc_war_score(d):
    s = 0
    if d["vxf_change"] <= -5: s += 30
    elif d["vxf_change"] < 0: s += 15
    if d["vix_change"] <= -5: s += 20
    elif d["vix_change"] < 0: s += 10
    if d["us2y_change"] < 0: s += 15
    if d["yield_spread"] < 0: s += 15
    if d["btc_change"] >= 3: s += 15
    if d["nq_change"] > 0: s += 10
    return s

def calc_peace_score(d):
    s = 0
    if d["nq_change"] > 0: s += 25
    if d["es_change"] > 0: s += 25
    if d["us10y_change"] < 0: s += 20
    if d["usd_jpy"] >= 150: s += 15
    if d["btc_change"] > 0: s += 15
    return s

# ============================
# メイン実行
# ============================
def main():
    data = get_market_data()
    mode = detect_mode(data["vix_price"])
    
    WAR_MAX, PEACE_MAX = 130, 115
    today = datetime.now().strftime("%Y.%m.%d")
    
    if mode == "war":
        raw = calc_war_score(data)
        scaled = scale_score(raw, WAR_MAX)
        zone = classify_zone(scaled, "war")
        msg = f"【{today} 戦時モード】\nデータ日：{data['data_date']}\n\nVIX現物: {data['vix_price']:.2f}\nVIX先物: {data['vxf_price']:.2f}\nスコア: {scaled}点\n判定: {zone}"
    
    elif mode == "peace":
        raw = calc_peace_score(data)
        scaled = scale_score(raw, PEACE_MAX)
        zone = classify_zone(scaled, "peace")
        msg = f"【{today} 平時モード】\nデータ日：{data['data_date']}\n\nNASDAQ: {data['nq_change']:.2f}%\nUSD/JPY: {data['usd_jpy']:.2f}\nスコア: {scaled}点\n判定: {zone}"
    
    else:
        w_scaled = scale_score(calc_war_score(data), WAR_MAX)
        p_scaled = scale_score(calc_peace_score(data), PEACE_MAX)
        msg = f"【{today} 移行期/不明】\nデータ日：{data['data_date']}\n\n戦時スコア: {w_scaled}点\n平時スコア: {p_scaled}点\n様子見を推奨します。"

    send_line(msg)

if __name__ == "__main__":
    main()
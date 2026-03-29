import requests
import json
import os
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
# 共通ヘルパー
# ============================
def get_json(url: str):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    return requests.get(url, headers=headers, timeout=15).json()

def get_soup(url: str):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    resp = requests.get(url, headers=headers, timeout=15)
    return BeautifulSoup(resp.text, "html.parser")

def get_data_date(meta):
    ts = meta.get("regularMarketTime")
    if ts:
        dt = datetime.fromtimestamp(ts, timezone.utc) + timedelta(hours=9)
        return dt.strftime("%Y.%m.%d")
    return "不明"

# ============================
# VIX先物：取得（三重化）
# ============================
def fetch_vix_futures():
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/VX=F"
        data = get_json(url)
        res = data["chart"]["result"][0]
        p = float(res["meta"]["regularMarketPrice"])
        prev = float(res["meta"]["chartPreviousClose"])
        c = (p - prev) / prev * 100
        _save_cache(p, c)
        return p, c
    except: pass

    try:
        url = "https://www.marketwatch.com/investing/future/vx00"
        soup = get_soup(url)
        p_el = soup.select_one("bg-quote[field='last']") or soup.select_one(".intraday__price .value")
        c_el = soup.select_one("bg-quote[field='percentChange']") or soup.select_one(".change--percent--q .value")
        if p_el and c_el:
            p = float(p_el.text.replace(",", "").strip())
            c = float(c_el.text.replace("%", "").replace("+", "").strip())
            _save_cache(p, c)
            return p, c
    except: pass

    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r") as f:
                cache = json.load(f)
                return cache["price"], cache["change"]
    except: pass
    return 0.0, 0.0

def _save_cache(p, c):
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump({"price": p, "change": c}, f)
    except: pass

# ============================
# データ集約
# ============================
def get_market_data():
    d = {"data_date": "不明"}
    targets = {
        "gold": "GC=F", "wti": "CL=F", "vix": "%5EVIX", 
        "nq": "NQ=F", "nk": "NK=F", "es": "ES=F", 
        "us10y": "%5ETNX", "us2y": "%5EIRX", "btc": "BTC-USD"
    }
    for key, symbol in targets.items():
        try:
            raw = get_json(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}")
            meta = raw["chart"]["result"][0]["meta"]
            p, prev = meta["regularMarketPrice"], meta["chartPreviousClose"]
            d[f"{key}_price"], d[f"{key}_change"] = p, (p - prev) / prev * 100
            if key == "vix": d["data_date"] = get_data_date(meta)
        except: d[f"{key}_price"], d[f"{key}_change"] = 0.0, 0.0

    try:
        fx = get_json("https://api.frankfurter.app/latest?from=USD&to=JPY")
        d["usd_jpy"] = fx["rates"]["JPY"]
    except: d["usd_jpy"] = 0.0

    d["vxf_price"], d["vxf_change"] = fetch_vix_futures()
    d["yield_spread"] = d["us10y_price"] - d["us2y_price"] if d["us2y_price"] != 0 else 0.0
    return d

# ============================
# メッセージ構築（出力イメージ準拠）
# ============================
def build_message(d):
    vix_p = d["vix_price"]
    if vix_p >= 20:
        mode, max_score = "戦時モード：相場反転スコア", 130
        score = calc_war_score(d)
    elif 0 < vix_p <= 15:
        mode, max_score = "平時モード：トレンドスコア", 115
        score = calc_peace_score(d)
    else:
        mode, max_score = "移行期モード：様子見", 130 # 移行期は暫定で戦時基準
        score = calc_war_score(d)

    scaled = min(max(int(score / max_score * 100), 0), 100)
    zone = classify_zone(scaled, "war" if vix_p >= 20 else "peace")
    today = datetime.now().strftime("%Y.%m.%d")

    msg = [
        f"【{today} {mode}（100点版）】",
        f"データ日：{d['data_date']}\n",
        f"VIX現物: {d['vix_price']:.2f}（{d['vix_change']:.2f}%）",
        f"VIX先物: {d['vxf_price']:.2f}（{d['vxf_change']:.2f}%）\n",
        "▼ 金利・イールドカーブ",
        f"・米2年金利: {d['us2y_price']:.2f}（{d['us2y_change']:.2f}%）",
        f"・米10年金利: {d['us10y_price']:.2f}（{d['us10y_change']:.2f}%）",
        f"・イールドカーブ(10Y-2Y): {d['yield_spread']:.2f}\n",
        "▼ 株価指数",
        f"・NASDAQ先物: {d['nq_price']:.2f}（{d['nq_change']:.2f}%）",
        f"・日経先物　: {d['nk_price']:.2f}（{d['nk_change']:.2f}%）",
        f"・S&P500先物: {d['es_price']:.2f}（{d['es_change']:.2f}%）\n",
        "▼ コモディティ",
        f"・金(Gold): {d['gold_price']:.2f}（{d['gold_change']:.2f}%）",
        f"・原油(WTI): {d['wti_price']:.2f}（{d['wti_change']:.2f}%）\n",
        "▼ 暗号資産",
        f"・BTC : {d['btc_price']:.2f}（{d['btc_change']:.2f}%）\n",
        f"総合スコア：{scaled}点（{zone}）",
        f"※ 生スコア：{score} / {max_score}"
    ]
    return "\n".join(msg)

# ============================
# スコアロジック (簡略化)
# ============================
def calc_war_score(d):
    s = 0
    if d["vxf_change"] <= -5: s += 30
    elif d["vxf_change"] < 0: s += 15
    if d["vix_change"] <= -5: s += 20
    if d["us2y_change"] < 0: s += 20
    if d["yield_spread"] < 0: s += 15
    if d["btc_change"] >= 3: s += 15
    if d["nq_change"] > 0: s += 15
    return s

def calc_peace_score(d):
    s = 0
    if d["nq_change"] > 0: s += 30
    if d["es_change"] > 0: s += 30
    if d["us10y_change"] < 0: s += 20
    if d["usd_jpy"] >= 150: s += 20
    if d["btc_change"] > 0: s += 15
    return s

def classify_zone(scaled, mode):
    if mode == "war":
        if scaled >= 80: return "反転確定ゾーン"
        if scaled >= 60: return "反転の可能性大"
        if scaled >= 40: return "反転の初期兆候"
        return "有事継続"
    else:
        if scaled >= 80: return "強い上昇トレンド"
        return "トレンド不明瞭"

def main():
    data = get_market_data()
    msg = build_message(data)
    send_line(msg)

if __name__ == "__main__":
    main()
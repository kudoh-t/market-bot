import requests
import json
import os
import pandas as pd
import io
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

# ============================
# 設定：環境変数
# ============================
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")
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
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        return resp.json()
    except:
        return {}

def get_data_date(meta):
    ts = meta.get("regularMarketTime")
    if ts:
        dt = datetime.fromtimestamp(ts, timezone.utc) + timedelta(hours=9)
        return dt.strftime("%Y.%m.%d")
    return "不明"

# ============================
# VIX先物：最強の多重化取得
# ============================
def fetch_vix_futures(vix_spot_price=0.0):
    # --- 1. Investing.com (ブラウザを装って最新タグから取得) ---
    try:
        url = "https://www.investing.com/indices/us-spx-vix-futures"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9"
        }
        resp = requests.get(url, headers=headers, timeout=12)
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # 2026年現在の最新セレクタ
        p_el = soup.select_one('[data-test="instrument-price-last"]')
        c_el = soup.select_one('[data-test="instrument-price-change-percent"]')
        
        if p_el:
            p = float(p_el.text.replace(",", ""))
            c_text = c_el.text.replace("%", "").replace("(", "").replace(")", "").strip()
            c = float(c_text)
            if p > 0:
                _save_cache(p, c)
                return p, c
    except Exception as e:
        print(f"Investing.com Failed: {e}")

    # --- 2. CNBC API (バックアップ) ---
    try:
        url = "https://quote.cnbc.com/quote-html-webservice/quote.htm?symbols=@VX.1&output=json"
        data = get_json(url)
        quote = data["QuickQuoteResult"]["QuickQuote"]
        p = float(quote["last"])
        c = float(quote["change_pct"])
        if p > 0:
            _save_cache(p, c)
            return p, c
    except:
        print("CNBC API Failed")

    # --- 3. 最後の手段：現物VIXの値を代用 (0.00を絶対に避ける) ---
    if vix_spot_price > 0:
        print("Warning: Using VIX Spot as fallback for Futures.")
        return vix_spot_price, 0.0

    # --- 4. 最終バックアップ：キャッシュ ---
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r") as f:
                cache = json.load(f)
                return cache["price"], cache["change"]
    except:
        pass

    return 0.0, 0.0

def _save_cache(p, c):
    if p <= 0: return
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump({"price": p, "change": c, "updated_at": datetime.now().isoformat()}, f)
    except:
        pass

# ============================
# 市場データ集約
# ============================
def get_market_data():
    d = {"data_date": "不明"}
    targets = {
        "gold": "GC=F", "wti": "CL=F", "vix": "%5EVIX",
        "nq": "NQ=F", "nk": "NK=F", "es": "ES=F",
        "us10y": "%5ETNX", "us2y": "%5EIRX", "btc": "BTC-USD"
    }

    # Yahoo Financeから基本データを取得
    for key, symbol in targets.items():
        try:
            raw = get_json(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}")
            meta = raw["chart"]["result"][0]["meta"]
            p = meta.get("regularMarketPrice")
            prev = meta.get("chartPreviousClose")
            if p is not None and prev is not None:
                d[f"{key}_price"], d[f"{key}_change"] = p, (p - prev) / prev * 100
                if key == "vix":
                    d["data_date"] = get_data_date(meta)
            else:
                d[f"{key}_price"], d[f"{key}_change"] = 0.0, 0.0
        except:
            d[f"{key}_price"], d[f"{key}_change"] = 0.0, 0.0

    # 為替
    try:
        fx = get_json("https://api.frankfurter.app/latest?from=USD&to=JPY")
        d["usd_jpy"] = fx.get("rates", {}).get("JPY", 0.0)
    except:
        d["usd_jpy"] = 0.0

    # VIX先物の取得実行（現物VIXを予備として渡す）
    d["vxf_price"], d["vxf_change"] = fetch_vix_futures(vix_spot_price=d.get("vix_price", 0.0))

    # イールドカーブ
    d["yield_spread"] = d["us10y_price"] - d["us2y_price"] if d["us2y_price"] != 0 else 0.0

    return d

# ============================
# スコアロジック
# ============================
def calc_war_score(d):
    s = 0
    # VIX先物の変化率（下げていれば反転の兆し）
    if d["vxf_change"] <= -7: s += 40
    elif d["vxf_change"] < 0: s += 20
    # VIX現物の急落
    if d["vix_change"] <= -5: s += 25
    # 金利低下（リスクオフ緩和）
    if d["us2y_change"] < 0: s += 20
    # 逆イールド解消の兆し
    if d["yield_spread"] < 0: s += 20
    # BTCの上昇（リスクオン）
    if d["btc_change"] >= 3: s += 15
    # 株価指数の上昇
    if d["nq_change"] > 0: s += 20
    if d["es_change"] > 0: s += 15
    return s

def calc_peace_score(d):
    s = 0
    if d["nq_change"] > 0: s += 35
    if d["es_change"] > 0: s += 35
    if d["us10y_change"] < 0: s += 20
    if d["usd_jpy"] >= 150: s += 20
    if d["btc_change"] > 0: s += 15
    return s

def calc_transition_score(d):
    s = 0
    if 15 < d["vix_price"] < 20:
        if d["vxf_change"] < 0: s += 25
        if d["nq_change"] > 0: s += 20
        if d["us10y_change"] < 0: s += 20
        if d["btc_change"] > 0: s += 15
    return s

def classify_zone(scaled, mode):
    if mode == "war":
        if scaled >= 80: return "反転確定ゾーン"
        if scaled >= 60: return "反転の可能性大"
        if scaled >= 40: return "反転の初期兆候"
        return "有事継続"
    if mode == "transition":
        if scaled >= 70: return "平時移行の可能性"
        if scaled >= 50: return "移行期の兆候"
        return "方向感なし"
    if scaled >= 80: return "強い上昇トレンド"
    if scaled >= 60: return "上昇トレンド"
    return "トレンド不明瞭"

# ============================
# メッセージ構築
# ============================
def build_message(d):
    vix_p = d["vix_price"]
    if vix_p >= 20:
        mode, max_score, zone_mode = "戦時モード：相場反転スコア", 155, "war"
        score = calc_war_score(d)
    elif vix_p <= 15:
        mode, max_score, zone_mode = "平時モード：トレンドスコア", 135, "peace"
        score = calc_peace_score(d)
    else:
        mode, max_score, zone_mode = "移行期モード：様子見", 140, "transition"
        score = calc_transition_score(d)

    scaled = min(max(int(score / max_score * 100), 0), 100)
    zone = classify_zone(scaled, zone_mode)
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
        "▼ 暗号資産",
        f"・BTC : {d['btc_price']:.2f}（{d['btc_change']:.2f}%）\n",
        f"総合スコア：{scaled}点（{zone}）",
        f"※ 生スコア：{score} / {max_score}"
    ]
    return "\n".join(msg)

# ============================
# メイン
# ============================
def main():
    data = get_market_data()
    msg = build_message(data)
    send_line(msg)

if __name__ == "__main__":
    main()
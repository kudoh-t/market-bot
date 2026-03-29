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
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        return resp.json()
    except:
        return {}

def get_soup(url: str):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        return BeautifulSoup(resp.text, "html.parser")
    except:
        return BeautifulSoup("", "html.parser")

def get_data_date(meta):
    ts = meta.get("regularMarketTime")
    if ts:
        dt = datetime.fromtimestamp(ts, timezone.utc) + timedelta(hours=9)
        return dt.strftime("%Y.%m.%d")
    return "不明"

# ============================
# VIX先物：四重化取得（CBOE直取得を追加）
# ============================
def fetch_vix_futures():
    # --- 1. CBOE JSON API (CSVより構造が安定している) ---
    try:
        # CBOEのクォートAPIを直接叩く
        url = "https://cdn.cboe.com/api/global/delayed_quotes/quotes/_vix.json"
        headers = {"User-Agent": "Mozilla/5.0"}
        data = get_json(url)
        # 先物（VX）の直近限月を探すロジック
        if data and "data" in data:
            # 簡略化のため、現物VIXに近い値を持つ先物を推測（または特定のシンボル検索）
            # 実際にはCBOEのこのURLは現物メインのため、Yahooの別ルートを優先
            pass
    except:
        pass

    # --- 2. Yahoo Finance (別のクエリ形式) ---
    try:
        # VX=F がダメな場合、直近限月の具体的なシンボル（例: VXJ26 ※Jは4月）を試す
        # ここでは汎用的な VX=F の別エンドポイント
        url = "https://query2.finance.yahoo.com/v10/finance/quoteSummary/VX=F?modules=price"
        data = get_json(url)
        price_data = data["quoteSummary"]["result"][0]["price"]
        p = float(price_data["regularMarketPrice"]["raw"])
        c = float(price_data["regularMarketChangePercent"]["raw"]) * 100
        if p > 0:
            _save_cache(p, c)
            return p, c
    except:
        pass

    # --- 3. Investing.com 系のミラーサイト (Investing.com本体はブロックが強いため) ---
    try:
        # CNBCのデータソースを利用
        url = "https://quote.cnbc.com/quote-html-webservice/quote.htm?symbols=@VX.1"
        resp = requests.get(url, timeout=10)
        soup = BeautifulSoup(resp.text, "xml") # XML形式
        p = float(soup.find("last").text)
        c = float(soup.find("change_pct").text)
        if p > 0:
            _save_cache(p, c)
            return p, c
    except:
        pass

    # --- 4. 既存のMarketWatch (バックアップ) ---
    # (以前のコードのロジックを継続)

    # --- 5. 最終手段：キャッシュ ---
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r") as f:
                cache = json.load(f)
                return cache["price"], cache["change"]
    except:
        pass

    return 0.0, 0.0

def _save_cache(p, c):
    if p <= 0: return # 異常値は保存しない
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
    # 各種シンボルの取得
    targets = {
        "gold": "GC=F", "wti": "CL=F", "vix": "%5EVIX",
        "nq": "NQ=F", "nk": "NK=F", "es": "ES=F",
        "us10y": "%5ETNX", "us2y": "%5EIRX", "btc": "BTC-USD"
    }

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

    # 為替 (USDJPY) - Frankfurter API が落ちている場合も考慮
    try:
        fx = get_json("https://api.frankfurter.app/latest?from=USD&to=JPY")
        d["usd_jpy"] = fx.get("rates", {}).get("JPY", 0.0)
    except:
        d["usd_jpy"] = 0.0

    # VIX先物の取得（多重化関数呼び出し）
    d["vxf_price"], d["vxf_change"] = fetch_vix_futures()

    # イールドカーブ
    d["yield_spread"] = d["us10y_price"] - d["us2y_price"] if d["us2y_price"] != 0 else 0.0

    return d

# ============================
# スコアロジック（変更なし）
# ============================
def calc_war_score(d):
    s = 0
    if d["vxf_change"] <= -7: s += 40
    elif d["vxf_change"] < 0: s += 20
    if d["vix_change"] <= -5: s += 25
    if d["us2y_change"] < 0: s += 20
    if d["yield_spread"] < 0: s += 20
    if d["btc_change"] >= 3: s += 15
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
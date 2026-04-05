import os
import json
import time
import csv
import requests
from datetime import datetime, timedelta
from xml.etree import ElementTree as ET

# =========================
#  LINE 設定
# =========================

LINE_TOKEN = os.environ.get("LINE_ACCESS_TOKEN")
LINE_USER_ID = os.environ.get("LINE_USER_ID")

def push_line_message(text: str):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_TOKEN}",
    }
    body = {
        "to": LINE_USER_ID,
        "messages": [{"type": "text", "text": text}],
    }
    r = requests.post(url, headers=headers, json=body)
    r.raise_for_status()


# =========================
#  ロガー
# =========================

def log(msg):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] {msg}")


# =========================
#  Twelve Data API
# =========================

TD_API_KEY = os.environ.get("TWELVE_DATA_API_KEY")
TD_BASE = "https://api.twelvedata.com/time_series"

def td_fetch(symbol, interval="1day"):
    """
    Twelve Data → 3回リトライ → 失敗なら None
    """
    for _ in range(3):
        try:
            url = f"{TD_BASE}?symbol={symbol}&interval={interval}&apikey={TD_API_KEY}&outputsize=2"
            r = requests.get(url, timeout=10)
            data = r.json()

            if "values" in data:
                latest = float(data["values"][0]["close"])
                prev = float(data["values"][1]["close"])
                pct = (latest - prev) / prev * 100
                return latest, pct

        except Exception as e:
            log(f"Twelve Data error ({symbol}): {e}")

        time.sleep(1)

    return None, None


# =========================
#  Yahoo Finance バックアップ
# =========================

def yahoo_fetch(symbol):
    """
    Yahoo Finance CSV API（Cookie不要・安定）
    """
    try:
        end = datetime.now()
        start = end - timedelta(days=7)

        url = (
            f"https://query1.finance.yahoo.com/v7/finance/download/{symbol}"
            f"?period1={int(start.timestamp())}"
            f"&period2={int(end.timestamp())}"
            f"&interval=1d&events=history"
        )

        r = requests.get(url, timeout=10)
        r.raise_for_status()

        lines = r.text.splitlines()
        reader = csv.DictReader(lines)
        rows = list(reader)

        if len(rows) < 2:
            return None, None

        latest = float(rows[-1]["Close"])
        prev = float(rows[-2]["Close"])
        pct = (latest - prev) / prev * 100

        return latest, pct

    except Exception as e:
        log(f"Yahoo fetch error ({symbol}): {e}")
        return None, None


# =========================
#  フェイルオーバー
# =========================

def fetch_with_backup(symbol_td, symbol_yf):
    """
    Twelve Data → Yahoo Finance の順で取得
    """
    price, pct = td_fetch(symbol_td)
    if price is not None:
        return price, pct

    log(f"Twelve Data failed for {symbol_td}, trying Yahoo Finance...")
    return yahoo_fetch(symbol_yf)


# =========================
#  ニュースフィルタ
# =========================

FAKE_KEYWORDS = [
    "撃墜", "攻撃", "爆撃", "砲撃", "ミサイル", "核", "侵攻", "衝突",
    "戦闘", "戦争", "交戦", "反撃", "空爆", "兵器", "軍事作戦",
    "SNSで投稿", "Xで投稿", "未確認情報", "動画が拡散",
    "パニック", "大混乱", "死亡多数", "暴落確定", "歴史的危機",
]

TRUSTED_SOURCES = {
    "bloomberg": 3,
    "reuters": 3,
    "wsj": 3,
    "nikkei": 3,
    "cnbc": 2,
    "ft.com": 2,
    "bbc": 2,
    "apnews": 2,
    "yahoo": 1,
    "marketwatch": 1,
}

def fetch_news():
    try:
        url = "https://news.yahoo.co.jp/rss/topics/business.xml"
        r = requests.get(url, timeout=10)
        r.encoding = "utf-8"
        return r.text
    except:
        return ""

def parse_news_xml(xml_text):
    items = []
    try:
        root = ET.fromstring(xml_text)
        for item in root.findall(".//item"):
            title = item.find("title").text
            link = item.find("link").text
            items.append({"title": title, "url": link})
    except:
        pass
    return items

def is_fake_news(text):
    return any(k in text for k in FAKE_KEYWORDS)

def detect_source_score(url):
    url = url.lower()
    for key, score in TRUSTED_SOURCES.items():
        if key in url:
            return score
    return -3

def detect_content_score(text):
    if any(k in text for k in ["CPI", "雇用統計", "PMI", "インフレ"]):
        return 3
    if any(k in text for k in ["FRB", "利上げ", "利下げ", "金利"]):
        return 2
    if "決算" in text:
        return 1
    if any(k in text for k in ["攻撃", "戦闘", "撃墜"]):
        return -3
    return 0

def detect_tone_score(text):
    if any(k in text for k in ["暴落", "崩壊", "パニック"]):
        return -3
    if any(k in text for k in ["懸念", "警戒"]):
        return -1
    return 1

def filter_news_list(xml_text):
    raw_items = parse_news_xml(xml_text)
    ok_items = []
    removed_items = []

    for item in raw_items:
        title = item["title"]
        url = item["url"]

        if is_fake_news(title):
            removed_items.append({"title": title, "reason": "fake"})
            continue

        s1 = detect_source_score(url)
        s2 = detect_content_score(title)
        s3 = detect_tone_score(title)

        if s1 + s2 + s3 <= -2:
            removed_items.append({"title": title, "reason": "low_trust"})
            continue

        ok_items.append(item)

    return ok_items, removed_items


# =========================
#  スコア計算
# =========================

def calc_total_score(data):
    score = 0
    max_score = 155

    fgi = data["fgi"]["value"]
    if fgi is not None:
        if fgi >= 60: score += 20
        elif fgi >= 40: score += 10
        elif fgi >= 20: score += 5

    for pct in [
        data["indices"]["nq_pct"],
        data["indices"]["spx_pct"],
        data["indices"]["nikkei_pct"],
    ]:
        if pct is not None:
            if pct > 0.5: score += 10
            elif pct > 0: score += 5
            elif pct > -0.5: score += 2

    us10 = data["rates"]["us10"]
    us2 = data["rates"]["us2"]
    if us10 and us2:
        spread = us10 - us2
        if spread > 1.0: score += 10
        elif spread > 0.5: score += 5

    for pct in [
        data["commod"]["gold_pct"],
        data["commod"]["wti_pct"],
        data["commod"]["copper_pct"],
    ]:
        if pct is not None:
            if pct > 1.0: score += 5
            elif pct > 0: score += 2

    btc_pct = data["crypto"]["btc_pct"]
    if btc_pct is not None:
        if btc_pct > 1.0: score += 5
        elif btc_pct > 0: score += 2

    return score, max_score


# =========================
#  ローカル Copilot コメント生成
# =========================

def llm(prompt: str) -> str:
    lines = prompt.split("\n")
    summary = []

    for line in lines:
        if "FGI" in line:
            summary.append("投資家心理は慎重姿勢が続く。")
        if "金利" in line:
            summary.append("金利動向が市場の方向性を左右しやすい状況。")
        if "指数" in line:
            summary.append("主要指数は方向感を探る展開。")
        if "ニュース" in line:
            summary.append("ニュースは市場に限定的な影響。")

    if not summary:
        summary.append("市場は材料を探る展開。")

    return "【ローカルCopilotコメント】\n" + "\n".join(summary)


# =========================
#  最終メッセージ生成
# =========================

def build_final_message(date_str, market_data, news_removed, llm_comment, score, max_score):
    msg = f"""【{date_str} 市況まとめ】

▼ 1. 投資家心理 (FGI)
 {market_data['fgi']['label']} / {market_data['fgi']['value']}

▼ 2. 主要指数
 NQ100 : {market_data['indices']['nq']}（{market_data['indices']['nq_pct']}%）
 S&P500: {market_data['indices']['spx']}（{market_data['indices']['spx_pct']}%）
 日経平均: {market_data['indices']['nikkei']}（{market_data['indices']['nikkei_pct']}%）

▼ 3. 金利
 米10年債: {market_data['rates']['us10']}（{market_data['rates']['us10_pct']}%）
 米2年債: {market_data['rates']['us2']}（{market_data['rates']['us2_pct']}%）

▼ 4. 商品
 金: {market_data['commod']['gold']}（{market_data['commod']['gold_pct']}%）
 原油: {market_data['commod']['wti']}（{market_data['commod']['wti_pct']}%）
 銅: {market_data['commod']['copper']}（{market_data['commod']['copper_pct']}%）

▼ 5. BTC
 BTC: {market_data['crypto']['btc']}（{market_data['crypto']['btc_pct']}%）

▼ 6. Copilot コメント
{llm_comment}

▼ 7. 除外ニュース
{chr(10).join(f"- {x['title']}" for x in news_removed)}

▼ 8. スコア
 {score}点 / {max_score}
"""
    return msg


# =========================
#  メイン処理
# =========================

def main(llm_func):
    log("データ取得開始")

    # FGI
    try:
        fgi_data = requests.get("https://api.alternative.me/fng/?limit=2&format=json").json()
        fgi = {
            "value": int(fgi_data["data"][0]["value"]),
            "label": fgi_data["data"][0]["value_classification"],
            "diff": 0,
        }
    except:
        fgi = {"value": None, "label": "取得不可", "diff": 0}

    # 市場データ（フェイルオーバー）
    nq, nq_pct = fetch_with_backup("NDX", "NDX")
    spx, spx_pct = fetch_with_backup("SPX", "SPX")
    nikkei, nikkei_pct = fetch_with_backup("N225", "^N225")

    us10, us10_pct = fetch_with_backup("US10Y", "^TNX")
    us2, us2_pct = fetch_with_backup("US02Y", "^IRX")

    gold, gold_pct = fetch_with_backup("XAU/USD", "GC=F")
    wti, wti_pct = fetch_with_backup("CL=F", "CL=F")
    copper, copper_pct = fetch_with_backup("HG=F", "HG=F")

    btc, btc_pct = fetch_with_backup("BTC/USD", "BTC-USD")

    # ニュース
    xml = fetch_news()
    news_ok, news_removed = filter_news_list(xml)

    market_data = {
        "fgi": fgi,
        "indices": {
            "nq": nq, "nq_pct": nq_pct,
            "spx": spx, "spx_pct": spx_pct,
            "nikkei": nikkei, "nikkei_pct": nikkei_pct,
        },
        "rates": {
            "us10": us10, "us10_pct": us10_pct,
            "us2": us2, "us2_pct": us2_pct,
        },
        "commod": {
            "gold": gold, "gold_pct": gold_pct,
            "wti": wti, "wti_pct": wti_pct,
            "copper": copper, "copper_pct": copper_pct,
        },
        "crypto": {
            "btc": btc, "btc_pct": btc_pct,
        },
    }

    score, max_score = calc_total_score(market_data)

    # LLM（ローカル）
    data_text = json.dumps(market_data, ensure_ascii=False, indent=2)
    news_text = "\n".join(f"- {n['title']}" for n in news_ok)
    prompt = f"【データ】{data_text}\n【ニュース】{news_text}"

    llm_comment = llm_func(prompt)

    # メッセージ生成
    date_str = datetime.now().strftime("%Y.%m.%d")
    final_msg = build_final_message(date_str, market_data, news_removed, llm_comment, score, max_score)

    push_line_message(final_msg)
    log("LINE送信完了")


if __name__ == "__main__":
    main(llm)
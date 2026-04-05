import os
import json
import requests
from datetime import datetime
import re
from xml.etree import ElementTree as ET

# =========================
#  LINE 設定
# =========================

LINE_TOKEN = os.environ.get("LINE_ACCESS_TOKEN")
LINE_USER_ID = os.environ.get("LINE_USER_ID")

def push_line_message(text: str):
    """LINEへメッセージ送信"""
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
    """Twelve Data で価格と前日比を取得"""
    try:
        url = f"{TD_BASE}?symbol={symbol}&interval={interval}&apikey={TD_API_KEY}&outputsize=2"
        r = requests.get(url, timeout=10)
        data = r.json()

        if "values" not in data:
            log(f"TwelveData error: {data}")
            return None, None

        latest = float(data["values"][0]["close"])
        prev = float(data["values"][1]["close"])
        pct = (latest - prev) / prev * 100
        return latest, pct

    except Exception as e:
        log(f"td_fetch error ({symbol}): {e}")
        return None, None


# ====== 各マーケットデータ ======

def fetch_index(symbol):
    return td_fetch(symbol)

def fetch_rate(symbol):
    return td_fetch(symbol)

def fetch_commodity(symbol):
    return td_fetch(symbol)

def fetch_btc():
    return td_fetch("BTC/USD")


# =========================
#  FGI（Fear & Greed Index）
# =========================

def fetch_fgi():
    try:
        url = "https://api.alternative.me/fng/?limit=2&format=json"
        r = requests.get(url, timeout=10)
        data = r.json()["data"][0]
        value = int(data["value"])
        label = data["value_classification"]
        return {"value": value, "label": label, "diff": 0}
    except:
        return {"value": None, "label": "取得不可", "diff": 0}


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
#  総合スコア（155点満点）
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
#  GS / MS プロンプト
# =========================

GS_PROMPT = """
あなたはゴールドマンサックスのマクロストラテジストです。
以下の市場データとニュースをもとに、構造的で簡潔な市況コメントを作成してください。
投資助言は禁止。
【データ】{data}
【ニュース】{news}
"""

MS_PROMPT = """
あなたはモルガン・スタンレーのマクロストラテジストです。
以下の市場データとニュースをもとに、慎重で需給重視の市況コメントを作成してください。
投資助言は禁止。
【データ】{data}
【ニュース】{news}
"""

def choose_style(score, vix_ratio, fgi_label):
    if score < 40 or (vix_ratio and vix_ratio > 0.95) or fgi_label == "極度の恐怖":
        return "MS"
    return "GS"


# =========================
#  Copilot API（OpenAI互換）
# =========================

from openai import OpenAI
client = OpenAI()

def llm(prompt):
    try:
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message["content"]
    except Exception as e:
        log(f"LLM error: {e}")
        return "（LLMエラーのためコメント生成に失敗しました）"


# =========================
#  最終メッセージ生成
# =========================

def build_final_message(date_str, market_data, news_removed, llm_comment, score, max_score):
    msg = f"""【{date_str} 🚨戦時モード：総合反転スコア】

▼ 1. 投資家心理 (FGI)
 【{market_data['fgi']['label']}】 指数: {market_data['fgi']['value']}（前日比：{market_data['fgi']['diff']}pt）

▼ 2. 主要指数先物
 NQ100 : {market_data['indices']['nq']}（{market_data['indices']['nq_pct']}%）
 S&P500: {market_data['indices']['spx']}（{market_data['indices']['spx_pct']}%）
 日経平均: {market_data['indices']['nikkei']}（{market_data['indices']['nikkei_pct']}%）

▼ 3. リスク指標 (VIX/VIX3M)
 比率: {market_data['vix']['ratio']}

▼ 4. 金利
 米10年債: {market_data['rates']['us10']}（{market_data['rates']['us10_pct']}%）
 米2年債: {market_data['rates']['us2']}（{market_data['rates']['us2_pct']}%）

▼ 5. 商品
 金: {market_data['commod']['gold']}（{market_data['commod']['gold_pct']}%）
 原油: {market_data['commod']['wti']}（{market_data['commod']['wti_pct']}%）
 銅: {market_data['commod']['copper']}（{market_data['commod']['copper_pct']}%）

▼ 6. BTC
 BTC: {market_data['crypto']['btc']}（{market_data['crypto']['btc_pct']}%）

▼ 7. Copilot マクロニュース総合コメント
{llm_comment}

▼ 8. 除外ニュース
{chr(10).join(f"- {x['title']}" for x in news_removed)}

▼ 9. Copilot総合スコア
 {score}点 / 100（素点: {score} / {max_score}）
"""
    return msg


# =========================
#  メイン処理
# =========================

def main(llm_func):
    log("データ取得開始")

    # FGI
    fgi = fetch_fgi()

    # 指数
    nq, nq_pct = fetch_index("NDX")
    spx, spx_pct = fetch_index("SPX")
    nikkei, nikkei_pct = fetch_index("N225")

    # 金利
    us10, us10_pct = fetch_rate("US10Y")
    us2, us2_pct = fetch_rate("US02Y")

    # コモディティ
    gold, gold_pct = fetch_commodity("XAU/USD")
    wti, wti_pct = fetch_commodity("CL")
    copper, copper_pct = fetch_commodity("COPPER")

    # BTC
    btc, btc_pct = fetch_btc()

    # ニュース
    xml = fetch_news()
    news_ok, news_removed = filter_news_list(xml)

    # 市場データまとめ
    market_data = {
        "fgi": fgi,
        "indices": {
            "nq": nq, "nq_pct": nq_pct,
            "spx": spx, "spx_pct": spx_pct,
            "nikkei": nikkei, "nikkei_pct": nikkei_pct,
        },
        "vix": {
            "ratio": None,  # VIX は後で追加可能
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

    # スコア計算
    score, max_score = calc_total_score(market_data)

    # GS / MS 自動切替
    style = choose_style(score, None, fgi["label"])
    log(f"選択されたスタイル: {style}")

    # LLM コメント生成
    data_text = json.dumps(market_data, ensure_ascii=False, indent=2)
    news_text = "\n".join(f"- {n['title']}" for n in news_ok)
    prompt = (GS_PROMPT if style == "GS" else MS_PROMPT).format(data=data_text, news=news_text)
    llm_comment = llm_func(prompt)

    # 最終メッセージ
    date_str = datetime.now().strftime("%Y.%m.%d")
    final_msg = build_final_message(date_str, market_data, news_removed, llm_comment, score, max_score)

    # LINE送信
    push_line_message(final_msg)
    log("LINE送信完了")


# =========================
#  エントリポイント
# =========================

if __name__ == "__main__":
    main(llm)
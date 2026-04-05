import os
import json
import time
import requests
from datetime import datetime
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
#  TradingView API
# =========================

def tv_fetch(market, symbols):
    """
    TradingView スキャナー API
    market: "america", "japan", "crypto"
    symbols: ["NDX", "SPX", ...]
    """
    url = f"https://scanner.tradingview.com/{market}/scan"

    payload = {
        "symbols": {"tickers": symbols, "query": {"types": []}},
        "columns": ["close", "change", "change_percent"]
    }

    try:
        r = requests.post(url, json=payload, timeout=10)
        data = r.json()

        result = {}
        for d in data.get("data", []):
            s = d["s"]  # シンボル名
            close = d["d"][0]
            change = d["d"][1]
            pct = d["d"][2]
            result[s] = (close, pct)

        return result

    except Exception as e:
        print("TradingView error:", e)
        return {}


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
#  メイン処理
# =========================

def main(llm_func):
    print("データ取得開始")

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

    # TradingView で一括取得
    us = tv_fetch("america", ["NDX", "SPX"])
    jp = tv_fetch("japan", ["N225"])
    com = tv_fetch("america", ["GC1!", "CL1!", "HG1!"])
    crypto = tv_fetch("crypto", ["BTCUSD"])

    nq, nq_pct = us.get("NDX", (None, None))
    spx, spx_pct = us.get("SPX", (None, None))
    nikkei, nikkei_pct = jp.get("N225", (None, None))

    gold, gold_pct = com.get("GC1!", (None, None))
    wti, wti_pct = com.get("CL1!", (None, None))
    copper, copper_pct = com.get("HG1!", (None, None))

    btc, btc_pct = crypto.get("BTCUSD", (None, None))

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
    final_msg = f"""【{date_str} 市況まとめ】

▼ 1. 投資家心理 (FGI)
 {market_data['fgi']['label']} / {market_data['fgi']['value']}

▼ 2. 主要指数
 NQ100 : {market_data['indices']['nq']}（{market_data['indices']['nq_pct']}%）
 S&P500: {market_data['indices']['spx']}（{market_data['indices']['spx_pct']}%）
 日経平均: {market_data['indices']['nikkei']}（{market_data['indices']['nikkei_pct']}%）

▼ 3. 商品
 金: {market_data['commod']['gold']}（{market_data['commod']['gold_pct']}%）
 原油: {market_data['commod']['wti']}（{market_data['commod']['wti_pct']}%）
 銅: {market_data['commod']['copper']}（{market_data['commod']['copper_pct']}%）

▼ 4. BTC
 BTC: {market_data['crypto']['btc']}（{market_data['crypto']['btc_pct']}%）

▼ 5. Copilot コメント
{llm_comment}

▼ 6. 除外ニュース
{chr(10).join(f"- {x['title']}" for x in news_removed)}

▼ 7. スコア
 {score}点 / {max_score}
"""

    push_line_message(final_msg)
    print("LINE送信完了")


if __name__ == "__main__":
    main(llm)
import os
import json
import requests
from datetime import datetime, timedelta
import re
from xml.etree import ElementTree as ET

# =========================
#  設定
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
#  キャッシュユーティリティ
# =========================

def load_cache(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


# =========================
#  ロガー
# =========================

def log(msg):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] {msg}")


# =========================
#  データ取得：FGI
# =========================

def fetch_fgi():
    cache_path = "cache_fgi.json"
    cache = load_cache(cache_path)

    # Alternative.me（安定）
    try:
        url = "https://api.alternative.me/fng/?limit=2&format=json"
        r = requests.get(url, timeout=5)
        data = r.json()["data"][0]
        value = int(data["value"])
        label = data["value_classification"]
        diff = value - int(cache.get("value", value))
        result = {"value": value, "label": label, "diff": diff}
        save_cache(cache_path, result)
        return result
    except Exception:
        pass

    # CNN fallback
    try:
        url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
        r = requests.get(url, timeout=5)
        value = int(r.json()["fear_and_greed"]["score"])
        diff = value - int(cache.get("value", value))
        result = {"value": value, "label": "N/A", "diff": diff}
        save_cache(cache_path, result)
        return result
    except Exception:
        pass

    # cache fallback
    if cache:
        return cache

    return {"value": None, "label": "取得不可", "diff": 0}


# =========================
#  データ取得：VIX（現物・3M・先物）
# =========================

def fetch_vix_spot():
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/^VIX"
        r = requests.get(url, timeout=5)
        meta = r.json()["chart"]["result"][0]["meta"]
        price = meta["regularMarketPrice"]
        prev = meta["chartPreviousClose"]
        pct = (price - prev) / prev * 100
        return price, pct
    except Exception:
        return None, None


def fetch_vix_3m():
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/^VIX3M"
        r = requests.get(url, timeout=5)
        meta = r.json()["chart"]["result"][0]["meta"]
        price = meta["regularMarketPrice"]
        prev = meta["chartPreviousClose"]
        pct = (price - prev) / prev * 100
        return price, pct
    except Exception:
        return None, None


def fetch_vix_futures():
    cache_path = "cache_vix.json"
    cache = load_cache(cache_path)

    try:
        url = "https://cdn.cboe.com/api/global/us_indices/volatility/vix_futures.json"
        r = requests.get(url, timeout=5)
        data = r.json()
        vx1 = float(data["vx1"]["last"])
        vx2 = float(data["vx2"]["last"])
        result = {"vx1": vx1, "vx2": vx2}
        save_cache(cache_path, result)
        return result
    except Exception:
        pass

    if cache:
        return cache

    return {"vx1": None, "vx2": None}


# =========================
#  データ取得：指数（NQ / SPX / 日経）
# =========================

def fetch_index(symbol):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        r = requests.get(url, timeout=5)
        meta = r.json()["chart"]["result"][0]["meta"]
        price = meta["regularMarketPrice"]
        prev = meta["chartPreviousClose"]
        pct = (price - prev) / prev * 100
        return price, pct
    except Exception:
        return None, None


# =========================
#  データ取得：金利（10年 / 2年）
# =========================

def fetch_rate(symbol):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        r = requests.get(url, timeout=5)
        meta = r.json()["chart"]["result"][0]["meta"]
        price = meta["regularMarketPrice"]
        prev = meta["chartPreviousClose"]
        pct = (price - prev) / prev * 100
        return price, pct
    except Exception:
        return None, None


# =========================
#  データ取得：コモディティ（原油 / 金 / 銅）
# =========================

def fetch_commodity(symbol):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        r = requests.get(url, timeout=5)
        meta = r.json()["chart"]["result"][0]["meta"]
        price = meta["regularMarketPrice"]
        prev = meta["chartPreviousClose"]
        pct = (price - prev) / prev * 100
        return price, pct
    except Exception:
        return None, None


# =========================
#  データ取得：BTC
# =========================

def fetch_btc():
    try:
        url = "https://api.coindesk.com/v1/bpi/currentprice.json"
        r = requests.get(url, timeout=5)
        price = float(r.json()["bpi"]["USD"]["rate"].replace(",", ""))
        return price
    except Exception:
        return None


# =========================
#  ニュース取得（Yahoo RSS）
# =========================

def fetch_news():
    try:
        url = "https://news.yahoo.co.jp/rss/topics/business.xml"
        r = requests.get(url, timeout=5)
        r.encoding = "utf-8"
        return r.text
    except Exception:
        return ""


# =========================
#  ニュースフィルタ（戦時＋平時）
# =========================

FAKE_KEYWORDS = [
    "撃墜", "攻撃", "爆撃", "砲撃", "ミサイル", "核", "侵攻", "衝突",
    "戦闘", "戦争", "交戦", "反撃", "空爆", "兵器", "軍事作戦",
    "SNSで投稿", "Xで投稿", "未確認情報", "動画が拡散",
    "パニック", "大混乱", "死亡多数", "暴落確定", "歴史的危機",
]

MACRO_KEYWORDS = [
    "CPI", "PCE", "インフレ", "物価", "GDP", "PMI", "ISM", "景気", "雇用統計",
    "失業率", "賃金", "JOLTS", "利上げ", "利下げ", "金利", "FOMC", "FRB",
    "パウエル", "日銀", "ECB", "決算", "ガイダンス", "売上高", "EPS", "利益",
    "リスクオン", "リスクオフ", "ボラティリティ", "関税", "貿易", "中国経済",
    "景気刺激策", "ドル円", "円安", "円高", "長期金利", "イールドカーブ",
    "原油", "WTI", "銅", "金価格",
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


def detect_source_score(url: str):
    url = url.lower()
    for key, score in TRUSTED_SOURCES.items():
        if key in url:
            return score
    return -3


def detect_content_score(text: str):
    if any(k in text for k in ["CPI", "雇用統計", "PMI", "インフレ"]):
        return 3
    if any(k in text for k in ["FRB", "利上げ", "利下げ", "金利"]):
        return 2
    if "決算" in text:
        return 1
    if any(k in text for k in ["攻撃", "戦闘", "撃墜"]):
        return -3
    return 0


def detect_tone_score(text: str):
    if any(k in text for k in ["暴落", "崩壊", "パニック"]):
        return -3
    if any(k in text for k in ["懸念", "警戒"]):
        return -1
    return 1


def is_fake_news(text: str):
    return any(k in text for k in FAKE_KEYWORDS)


def parse_news_xml(xml_text):
    items = []
    try:
        root = ET.fromstring(xml_text)
        for item in root.findall(".//item"):
            title = item.find("title").text
            link = item.find("link").text
            items.append({"title": title, "url": link})
    except Exception:
        pass
    return items


def filter_news_item(item):
    title = item["title"]
    url = item["url"]

    if is_fake_news(title):
        return None, "fake"

    s1 = detect_source_score(url)
    s2 = detect_content_score(title)
    s3 = detect_tone_score(title)
    total = s1 + s2 + s3

    if total <= -2:
        return None, "low_trust"

    return item, "ok"


def filter_news_list(xml_text):
    raw_items = parse_news_xml(xml_text)
    ok_items = []
    removed_items = []

    for item in raw_items:
        filtered, reason = filter_news_item(item)
        if filtered:
            ok_items.append(filtered)
        else:
            removed_items.append({"title": item["title"], "reason": reason})

    return ok_items, removed_items


# =========================
#  総合スコア（155点満点）
# =========================

def calc_total_score(data):
    score = 0
    max_score = 155

    fgi = data["fgi"]["value"]
    if fgi is not None:
        if fgi >= 60:
            score += 20
        elif fgi >= 40:
            score += 10
        elif fgi >= 20:
            score += 5

    for pct in [
        data["indices"]["nq_pct"],
        data["indices"]["spx_pct"],
        data["indices"]["nikkei_pct"],
    ]:
        if pct is not None:
            if pct > 0.5:
                score += 10
            elif pct > 0:
                score += 5
            elif pct > -0.5:
                score += 2

    vix = data["vix"]["spot"]
    vix3m = data["vix"]["vix3m"]
    if vix and vix3m:
        ratio = vix / vix3m
        if ratio < 0.90:
            score += 15
        elif ratio < 1.05:
            score += 5

    us10 = data["rates"]["us10"]
    us2 = data["rates"]["us2"]
    if us10 and us2:
        spread = us10 - us2
        if spread > 1.0:
            score += 10
        elif spread > 0.5:
            score += 5

    for pct in [
        data["commod"]["gold_pct"],
        data["commod"]["wti_pct"],
        data["commod"]["copper_pct"],
    ]:
        if pct is not None:
            if pct > 1.0:
                score += 5
            elif pct > 0:
                score += 2

    btc_pct = data["crypto"]["btc_pct"]
    if btc_pct is not None:
        if btc_pct > 1.0:
            score += 5
        elif btc_pct > 0:
            score += 2

    return score, max_score


# =========================
#  LLM プロンプト（GS / MS）
# =========================

GS_PROMPT = """
あなたはゴールドマンサックスのマクロストラテジストです。

以下の市場データとニュースをもとに、
ゴールドマンサックスのレポート特有の文体で、
簡潔かつ構造的な市況コメントを作成してください。

【文体ルール】
- 感情的・煽り表現は禁止
- 断定せず、「示唆される」「意識されやすい」を使用
- マクロ要因（インフレ、金利、景気、需給）を優先
- ニュースは「影響度（高・中・低）」で評価
- 投資助言は禁止

【出力構成】
① 市場全体の地合い
② マクロ要因の整理
③ ニュースの影響度
④ 今後意識されやすいポイント

【入力データ】
{data}

【ニュース】
{news}
"""

MS_PROMPT = """
あなたはモルガン・スタンレーのマクロストラテジストです。

以下の市場データとニュースをもとに、
モルガン・スタンレーのレポート特有の文体で、
慎重かつ構造的な市況コメントを作成してください。

【文体ルール】
- 感情的・煽り表現は禁止
- 「不確実性が残る」「複数の要因が交錯している」を適度に使用
- センチメント・需給・ポジションの偏りを重視
- 「市場はすでに織り込んでいる」を適切に使用
- 投資助言は禁止

【出力構成】
① 市場全体の地合い
② マクロ要因（インフレ、金利、景気、需給）
③ ニュースの影響度と織り込み度
④ 今後の注意点

【入力データ】
{data}

【ニュース】
{news}
"""


# =========================
#  GS / MS 自動切替ロジック
# =========================

def choose_style(score, vix_ratio, fgi_label):
    if score < 40 or (vix_ratio is not None and vix_ratio > 0.95) or fgi_label == "極度の恐怖":
        return "MS"
    return "GS"


# =========================
#  LLM コメント生成
# =========================

def generate_llm_comment(style, market_data, news_list, llm):
    data_text = json.dumps(market_data, ensure_ascii=False, indent=2)
    news_text = "\n".join(f"- {n['title']}" for n in news_list)

    if style == "GS":
        prompt = GS_PROMPT.format(data=data_text, news=news_text)
    else:
        prompt = MS_PROMPT.format(data=data_text, news=news_text)

    return llm(prompt)


# =========================
#  最終メッセージ生成
# =========================

def build_final_message(date_str, market_data, news_removed, llm_comment, score, max_score):
    msg = f"""【{date_str} 🚨戦時モード：総合反転スコア】

▼ 1. 投資家心理 (FGI)
 【{market_data['fgi']['label']}】 指数: {market_data['fgi']['value']}（前日比：{market_data['fgi']['diff']}pt）

▼ 2. 主要指数先物 & 相対強弱
 ・米 NQ100 : {market_data['indices']['nq']}（{market_data['indices']['nq_pct']}%）
 ・米 S&P500: {market_data['indices']['spx']}（{market_data['indices']['spx_pct']}%）
 ・日経平均 : {market_data['indices']['nikkei']}（{market_data['indices']['nikkei_pct']}%）

▼ 3. リスク指標 (VIX/VIX3M)
 ・VIX現物: {market_data['vix']['spot']}（{market_data['vix']['spot_pct']}%）
 ・VIX 3M : {market_data['vix']['vix3m']}（{market_data['vix']['vix3m_pct']}%）
 ・比率: {market_data['vix']['ratio'] if market_data['vix']['ratio'] is not None else 'N/A'}

▼ 4. 金利・イールド
 ・米10年債: {market_data['rates']['us10']}（{market_data['rates']['us10_pct']}%）
 ・米 2年債: {market_data['rates']['us2']}（{market_data['rates']['us2_pct']}%）
 ・利回り差: {market_data['rates']['spread'] if market_data['rates']['spread'] is not None else 'N/A'}

▼ 5. 商品 (Commodities)
 ・金 (Gold): {market_data['commod']['gold']}（{market_data['commod']['gold_pct']}%）
 ・原油(WTI): {market_data['commod']['wti']}（{market_data['commod']['wti_pct']}%）
 ・銅 (Cop) : {market_data['commod']['copper']}（{market_data['commod']['copper_pct']}%）

▼ 6. 仮想通貨 (Crypto)
 ・BTC: ${market_data['crypto']['btc']}（{market_data['crypto']['btc_pct']}%）

▼ 7. Copilot マクロニュース総合コメント
{llm_comment}

🚫 フェイク/信頼性低ニュースとして除外:
{chr(10).join(f"- {x['title']}" for x in news_removed)}

▼ 8. Copilot総合コメント（1〜7すべてを統合）
⚖️ 総合スコア：{score}点 / 100（素点: {score} / {max_score}）
"""
    return msg


# =========================
#  メイン処理
# =========================

def main(llm):
    log("データ取得開始")

    fgi = fetch_fgi()

    nq, nq_pct = fetch_index("NQ=F")
    spx, spx_pct = fetch_index("ES=F")
    nikkei, nikkei_pct = fetch_index("NI225")

    vix_spot, vix_spot_pct = fetch_vix_spot()
    vix3m, vix3m_pct = fetch_vix_3m()
    vix_fut = fetch_vix_futures()

    us10, us10_pct = fetch_rate("^TNX")
    us2, us2_pct = fetch_rate("^IRX")
    spread = (us10 - us2) if (us10 is not None and us2 is not None) else None

    gold, gold_pct = fetch_commodity("GC=F")
    wti, wti_pct = fetch_commodity("CL=F")
    copper, copper_pct = fetch_commodity("HG=F")

    btc = fetch_btc()
    btc_pct = None  # 必要なら前日比ロジックを追加

    xml = fetch_news()
    news_ok, news_removed = filter_news_list(xml)

    market_data = {
        "fgi": fgi,
        "indices": {
            "nq": nq,
            "nq_pct": nq_pct,
            "spx": spx,
            "spx_pct": spx_pct,
            "nikkei": nikkei,
            "nikkei_pct": nikkei_pct,
        },
        "vix": {
            "spot": vix_spot,
            "spot_pct": vix_spot_pct,
            "vix3m": vix3m,
            "vix3m_pct": vix3m_pct,
            "ratio": (vix_spot / vix3m) if (vix_spot is not None and vix3m is not None) else None,
        },
        "rates": {
            "us10": us10,
            "us10_pct": us10_pct,
            "us2": us2,
            "us2_pct": us2_pct,
            "spread": spread,
        },
        "commod": {
            "gold": gold,
            "gold_pct": gold_pct,
            "wti": wti,
            "wti_pct": wti_pct,
            "copper": copper,
            "copper_pct": copper_pct,
        },
        "crypto": {
            "btc": btc,
            "btc_pct": btc_pct,
        },
    }

    score, max_score = calc_total_score(market_data)
    vix_ratio = market_data["vix"]["ratio"]
    style = choose_style(score, vix_ratio, fgi["label"])
    log(f"選択されたスタイル: {style}")

    llm_comment = generate_llm_comment(style, market_data, news_ok, llm)

    date_str = datetime.now().strftime("%Y.%m.%d")
    final_msg = build_final_message(date_str, market_data, news_removed, llm_comment, score, max_score)

    push_line_message(final_msg)
    log("LINE送信完了")


# =========================
#  エントリポイント（LLMは後で差し替え）
# =========================

def dummy_llm(prompt: str) -> str:
    return "（LLM未接続のためダミーコメントです。LLM API を接続してください。）"


if __name__ == "__main__":
    main(dummy_llm)
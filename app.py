import os
import json
import pickle
from datetime import datetime, timezone, timedelta

import requests
from bs4 import BeautifulSoup

# ============================
# 設定：環境変数
# ============================
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")

CACHE_FILE = "market_cache.pkl"

# ============================
# キャッシュ関連
# ============================
def load_prev_data():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "rb") as f:
                return pickle.load(f)
        except Exception:
            return {}
    return {}

def save_data_cache(d):
    try:
        with open(CACHE_FILE, "wb") as f:
            pickle.dump(d, f)
    except Exception as e:
        print(f"キャッシュ保存エラー: {e}")

# ============================
# LINE送信
# ============================
def send_line(text: str):
    if not LINE_ACCESS_TOKEN or not LINE_USER_ID:
        print("LINE設定なし。標準出力:\n", text)
        return
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_ACCESS_TOKEN}",
    }
    body = {"to": LINE_USER_ID, "messages": [{"type": "text", "text": text}]}
    try:
        res = requests.post(url, headers=headers, data=json.dumps(body), timeout=10)
        res.raise_for_status()
    except Exception as e:
        print(f"LINE送信エラー: {e}")

# ============================
# 判定ロジック
# ============================
def get_fgi_detail(now_val, prev_val):
    if now_val is None:
        return "⚠️FGI取得失敗"
    if now_val <= 25:
        status = "極度の恐怖"
    elif now_val <= 45:
        status = "恐怖"
    elif now_val <= 55:
        status = "中立"
    elif now_val <= 75:
        status = "強欲"
    else:
        status = "極度の強欲"
    change = f"（前日比：{now_val - prev_val:+.0f}pt）" if prev_val is not None else ""
    return f"【{status}】 指数: {now_val} {change}"

def get_vix_analysis(v_spot, v_fut):
    if v_spot is None:
        return "⚠️VVIXデータ欠損"

    # ① VIX先物が欠損：現物だけで判断
    if v_fut is None:
        if v_spot >= 30:
            return "⚠️先物欠損：VIXは非常に高く、市場は強い警戒状態です。"
        elif v_spot >= 25:
            return "⚠️先物欠損：VIXは高水準で、警戒感が強い状況です。"
        elif v_spot >= 20:
            return "⚠️先物欠損：VIXはやや高く、慎重姿勢が続いています。"
        else:
            return "⚠️先物欠損：VIXは低めで、市場は落ち着きつつあります。"

    # ② 先物が現物とほぼ一致（代用の可能性）
    if abs(v_spot - v_fut) < 0.01:
        if v_spot >= 30:
            return "⚠️先物不明：VIXは非常に高く、市場は強い警戒状態です。"
        elif v_spot >= 25:
            return "⚠️先物不明：VIXは高水準で、警戒感が強い状況です。"
        elif v_spot >= 20:
            return "⚠️先物不明：VIXはやや高く、慎重姿勢が続いています。"
        else:
            return "⚠️先物不明：VIXは低めで、市場は落ち着きつつあります。"

    # ③ 通常ロジック
    diff = v_spot - v_fut
    if diff > 0.5:
        return f"🚨異常(逆転)：現物が先物を{diff:.2f}上回るパニック。反転間近。"
    return "✅正常：市場は落ち着いています。"

def get_yield_detail(spread):
    if spread is None:
        return "⚠️データ不足。"
    if spread < 0:
        return "🚨逆イールド：景気後退の強い予兆。"
    if spread > 0.7:
        return "🔥急拡大：金利暴走による価格調整に注意。"
    return "✅順イールド：金利体系は安定。"

def get_commodities_analysis(gold_c, wti_c, cop_c):
    if any(v is None for v in [gold_c, wti_c, cop_c]):
        return "⚠️商品データ不足。"
    if gold_c > 0.5 and wti_c > 1.0:
        return "🚨【有事・インフレ】金と原油が同時高。株に重石。"
    if gold_c > 0.5 and cop_c < -1.0:
        return "📉【景気後退懸念】銅安・金高。安全資産へ逃避。"
    if cop_c > 1.0 and wti_c > 1.0:
        return "🏗️【需要増】景気敏感資源が堅調。株に追い風。"
    return "⚖️【中立】明確なコモディティシグナルなし。"

def get_btc_comment(btc_change):
    if btc_change is None:
        return "⚠️BTC取得失敗。"
    if btc_change > 3.0:
        return "🚀【リスクオン】投機資金が旺盛。強気。"
    if btc_change < -3.0:
        return "💀【パニック】資金流出。株への波及警戒。"
    return "⚖️【安定】リスク許容度は維持。"

def get_equity_relative_comment(nk_c, nq_c, es_c):
    valid_us = [c for c in [nq_c, es_c] if c is not None]
    if nk_c is None or not valid_us:
        return "⚠️相対強弱：データ不足。"
    us_avg = sum(valid_us) / len(valid_us)
    diff = nk_c - us_avg
    if diff >= 0.5:
        return f"🇯🇵日本優位（乖離:{diff:+.2f}%）"
    if diff <= -0.5:
        return f"🇺🇸米国優位（乖離:{diff:+.2f}%）"
    return "⚖️日米拮抗"
# ============================
# データ取得
# ============================
def fetch_yahoo(symbol):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
        m = res["chart"]["result"][0]["meta"]
        p = m["regularMarketPrice"]
        c = (p - m["chartPreviousClose"]) / m["chartPreviousClose"] * 100
        return p, c
    except Exception:
        return None, None

def fetch_fgi_raw():
    try:
        url = "https://api.alternative.me/fng/?limit=2&format=json"
        res = requests.get(url, timeout=10).json()
        now_val = int(res["data"][0]["value"])
        prev_val = int(res["data"][1]["value"])
        return now_val, prev_val
    except Exception:
        return None, None

def fetch_vix_future_raw():
    urls = [
        "https://www.investing.com/indices/volatility-s-p-500-futures",
        "https://www.investing.com/indices/volatility-s-p-500-futures?cid=44336",
        "https://www.investing.com/indices/volatility-s-p-500-futures?cid=44337",
    ]
    headers = {"User-Agent": "Mozilla/5.0"}

    for url in urls:
        try:
            html = requests.get(url, headers=headers, timeout=2).text
            soup = BeautifulSoup(html, "html.parser")
            price_el = soup.select_one("div[data-test='instrument-price-last']")
            change_el = soup.select_one("span[data-test='instrument-price-change-percent']")
            if price_el and change_el:
                price = float(price_el.text.replace(",", ""))
                change = float(
                    change_el.text.replace("%", "").replace("+", "").replace("−", "-")
                )
                return price, change
        except Exception:
            continue

    p, c = fetch_yahoo("VX=F")
    if p is not None:
        return p, c

    return None, None

def fill_with_prev(d, prev, key_price, key_change):
    if d.get(key_price) is None and prev.get(key_price) is not None:
        d[key_price] = prev[key_price]
        d[key_change] = 0.0

def get_market_data():
    d = {}
    prev = load_prev_data()

    # FGI：失敗 → 前回値 → それもなければ中立50
    fgi_now, fgi_prev = fetch_fgi_raw()
    if fgi_now is None:
        if prev.get("fgi_score") is not None:
            fgi_now = prev.get("fgi_score")
            fgi_prev = prev.get("fgi_prev")
        else:
            fgi_now = 50
            fgi_prev = 50
    d["fgi_score"], d["fgi_prev"] = fgi_now, fgi_prev

    # VIX
    d["vix_p"], d["vix_c"] = fetch_yahoo("%5EVIX")
    d["vxf_p"], d["vxf_c"] = fetch_vix_future_raw()

    # 株・商品・金利
    targets = {
        "nq": "NQ=F",
        "es": "ES=F",
        "nk": "NK=F",
        "gold": "GC=F",
        "wti": "CL=F",
        "cop": "HG=F",
        "u10": "%5ETNX",
        "btc": "BTC-USD",
    }
    for k, s in targets.items():
        d[f"{k}_p"], d[f"{k}_c"] = fetch_yahoo(s)

    # 2年債（代替候補）
    d["u2_p"], d["u2_c"] = None, None
    for s in ["2Y=F", "^IRX", "^ZYY"]:
        p, c = fetch_yahoo(s)
        if p is not None:
            d["u2_p"], d["u2_c"] = p, c
            break

    # 欠損補完
    for key in ["vix", "vxf", "nq", "es", "nk", "gold", "wti", "cop", "u10", "u2", "btc"]:
        fill_with_prev(d, prev, f"{key}_p", f"{key}_c")

    # VIX先物が完全欠損 → 現物で代用
    if d.get("vxf_p") is None and d.get("vix_p") is not None:
        d["vxf_p"] = d["vix_p"]
        d["vxf_c"] = 0.0

    # イールド差
    d["spread"] = (
        (d.get("u10_p") - d.get("u2_p"))
        if d.get("u10_p") is not None and d.get("u2_p") is not None
        else None
    )

    # 日付
    d["date"] = datetime.now(timezone(timedelta(hours=9))).strftime("%Y.%m.%d")

    save_data_cache(d)
    return d

# ============================
# Copilot ローカル評価（旧）
# ============================
def copilot_comment(report: str) -> str:
    text = report.lower()
    if "極度の恐怖" in report or "vix現物" in report and "20" in report:
        return "市場は警戒感が強く、リスク回避姿勢が続く状況です。"
    if "強欲" in report or "上昇" in report:
        return "投資家心理は改善傾向で、リスク選好が戻りつつあります。"
    return "市場は方向感に乏しく、慎重姿勢が続いています。"
# ============================
# 戦時／平時ニューステンプレ
# ============================
def generate_news_block(mode):
    news_templates = {
        "war": [
            "中東情勢は依然不安定。イランの報復可能性が市場のリスク許容度を抑制。",
            "ウクライナ前線は膠着。欧州エネルギー供給懸念が再浮上。",
            "トランプ政権の関税強化発言が市場に波及。ドル高圧力が継続。",
            "FRB高官がインフレ鈍化の遅れを指摘。利下げ時期の後ずれ観測が強まる。",
            "原油は供給不安で堅調。金は安全資産需要で上昇基調。",
        ],
        "peace": [
            "中東情勢は落ち着きを取り戻し、原油供給は安定方向。",
            "ウクライナ情勢では停戦協議が進展し、欧州のエネルギー不安が後退。",
            "トランプ政権は企業減税や規制緩和を推進し、市場心理を下支え。",
            "FRBはインフレ鈍化を確認し、利下げ期待が高まる。",
            "原油・金は落ち着いた値動きで、需給バランスが安定。",
        ],
    }
    selected = news_templates.get(mode, [])
    return "\n".join([f"・{item}" for item in selected])


# ============================
# Copilot’s View（戦時3／平時3）
# ============================
def generate_copilot_view(mode, pattern=1):
    war_patterns = {
        1: "地政学リスクが市場心理を圧迫し、反発力は限定的です。原油・金の上昇は典型的な戦時モードのシグナルで、キャッシュ保護が合理的です。",
        2: "金利差の拡大と地政学不安が重なり、株式市場は上値が重い展開です。無理な逆張りよりも、下落の第二波に備える局面です。",
        3: "投資家心理は極度の恐怖に傾き、リスク回避姿勢が鮮明です。反転の兆しは弱く、守りを固める戦略が適切です。",
    }

    peace_patterns = {
        1: "地政学リスクが後退し、投資家心理は改善傾向です。金利低下とともに株式市場の反発余地が広がっています。",
        2: "企業決算や経済指標が堅調で、リスクオンの流れが強まっています。押し目買いが機能しやすい環境です。",
        3: "市場は安定し、資金は株式へ回帰しています。金利・為替・コモディティがバランスよく推移し、上昇トレンドが持続しやすい状況です。",
    }

    if mode == "war":
        return war_patterns.get(pattern, "")
    else:
        return peace_patterns.get(pattern, "")


# ============================
# キーワード辞書（JSON形式）
# ============================
keywords = {
    "war": {
        "iran": [
            "報復", "対抗措置", "ミサイル", "革命防衛隊", "核開発",
            "制裁強化", "ホルムズ海峡", "供給不安", "タンカー攻撃",
            "シーア派", "代理勢力", "レッドライン"
        ],
        "ukraine": [
            "前線膠着", "攻勢", "軍事支援", "NATO", "制空権",
            "インフラ攻撃", "停戦交渉", "領土問題", "長期化",
            "欧州エネルギー", "天然ガス", "制裁"
        ],
        "trump": [
            "関税強化", "対中強硬", "ドル高", "移民政策",
            "国防費増額", "軍事姿勢", "外交不確実性",
            "FRB圧力", "金融政策発言", "政策リスク"
        ]
    },
    "peace": {
        "iran": [
            "緊張緩和", "核合意", "制裁緩和", "供給安定",
            "地域対話", "仲介外交", "停戦合意"
        ],
        "ukraine": [
            "停戦協議", "復興支援", "欧州安定化",
            "エネルギー正常化", "国際支援", "和平ロードマップ"
        ],
        "trump": [
            "税制改革", "規制緩和", "企業減税",
            "インフラ投資", "雇用創出", "市場フレンドリー"
        ]
    }
}


# ============================
# メッセージ構築（ニュース＋Copilot’s View 統合）
# ============================
def build_message(d):
    prev_data = load_prev_data()
    vix_p = d.get("vix_p") or 0
    prev_vix = prev_data.get("vix_p") or 0
    fgi = d.get("fgi_score") or 50

    # 戦時/平時/移行モード判定
    if vix_p >= 25 or fgi <= 20:
        mode = "war"
        mode_title = "🚨戦時モード：総合反転スコア"
    elif vix_p <= 18 and fgi >= 40:
        mode = "peace"
        mode_title = "🍀平時モード：トレンドスコア"
    else:
        mode = "war" if vix_p >= 20 else "peace"
        if vix_p >= 20 and prev_vix < 20:
            mode_title = "⚠️移行モード：警戒開始"
        elif vix_p < 20 and prev_vix >= 20:
            mode_title = "🔄移行モード：沈静化の兆し"
        else:
            mode_title = "⚠️移行モード：警戒継続"

    # スコア計算（既存ロジック）
    score = 0
    max_score = 155

    if (d.get("nq_c") or 0) > 0:
        score += 25
    if (d.get("es_c") or 0) > 0:
        score += 20
    if (d.get("nk_c") or 0) > 0:
        score += 20

    if vix_p >= 30:
        score += 25
    elif vix_p >= 25:
        score += 15
    elif vix_p >= 20:
        score += 5

    if (d.get("spread") is not None) and d["spread"] < 0:
        score += 20

    if (d.get("btc_c") or 0) >= 3:
        score += 20

    scaled = min(max(int(score / max_score * 100), 0), 100)

    def fmt(p, c, dec=2):
        return f"{p:.{dec}f}（{c:+.2f}%）" if p is not None else "取得失敗"

    # ここまでが既存の ▼1〜6
    # ▼1〜6（既存部分）
    msg = [
        f"【{d.get('date')} {mode_title}】\n",
        "▼ 1. 投資家心理 (FGI)",
        f" {get_fgi_detail(d.get('fgi_score'), d.get('fgi_prev'))}\n",

        "▼ 2. 主要指数先物 & 相対強弱",
        f" ・米 NQ100 : {fmt(d.get('nq_p'), d.get('nq_c'))}",
        f" ・米 S&P500: {fmt(d.get('es_p'), d.get('es_c'))}",
        f" ・日経平均 : {fmt(d.get('nk_p'), d.get('nk_c'))}",
        f" 💡 {get_equity_relative_comment(d.get('nk_c'), d.get('nq_c'), d.get('es_c'))}\n",

        "▼ 3. リスク指標 (VIX)",
        f" ・VIX現物: {fmt(d.get('vix_p'), d.get('vix_c'))}",
        f" ・VIX先物: {fmt(d.get('vxf_p'), d.get('vxf_c'))}",
        f" 💡 {get_vix_analysis(d.get('vix_p'), d.get('vxf_p'))}\n",

        "▼ 4. 金利・イールド",
        f" ・米10年債: {fmt(d.get('u10_p'), d.get('u10_c'))}",
        f" ・米 2年債: {fmt(d.get('u2_p'), d.get('u2_c'))}",
        (
            f" ・利回り差: {d.get('spread'):.3f}"
            if d.get("spread") is not None
            else " ・利回り差: 失敗"
        ),
        f" 💡 {get_yield_detail(d.get('spread'))}\n",

        "▼ 5. 商品 (Commodities)",
        f" ・金 (Gold): {fmt(d.get('gold_p'), d.get('gold_c'), 1)}",
        f" ・原油(WTI): {fmt(d.get('wti_p'), d.get('wti_c'))}",
        f" ・銅 (Cop) : {fmt(d.get('cop_p'), d.get('cop_c'), 3)}",
        f" 💡 {get_commodities_analysis(d.get('gold_c'), d.get('wti_c'), d.get('cop_c'))}\n",

        "▼ 6. 仮想通貨 (Crypto)",
        f" ・BTC: ${fmt(d.get('btc_p'), d.get('btc_c'), 0)}",
        f" 💡 {get_btc_comment(d.get('btc_c'))}\n",

        f"⚖️ 総合スコア：{scaled}点 / 100 （素点: {score} / {max_score}）",
        f" {'📈 打診買い検討' if scaled >= 50 else '🌑 キャッシュ保護優先'}\n",
        "--------------------------",
    ]

    # ▼ 7. ニュース（戦時／平時切替）
    news_block = generate_news_block(mode)
    msg.append("▼ 7. 主要ニュース")
    msg.append(news_block)
    msg.append("--------------------------")

    # Copilot’s View（戦時3／平時3からランダム or 固定）
    view = generate_copilot_view(mode, pattern=1)
    msg.append("--- 🤖 Copilot's View ---")
    msg.append(view)

    return "\n".join(msg)


# ============================
# メイン
# ============================
def main():
    data = get_market_data()
    report = build_message(data)
    send_line(report)


if __name__ == "__main__":
    main()
# ============================
# ニュースRSS取得（Yahoo Japan）
# ============================
import xml.etree.ElementTree as ET

NEWS_FEEDS = [
    "https://news.yahoo.co.jp/rss/topics/world.xml",
    "https://news.yahoo.co.jp/rss/topics/business.xml",
    "https://news.yahoo.co.jp/rss/topics/economy.xml",
]

def fetch_rss_news(max_items=10):
    """
    YahooニュースRSSから最新ニュースを取得し、
    タイトル・URL・出所（source）を抽出して返す。
    """
    news_list = []

    for feed in NEWS_FEEDS:
        try:
            res = requests.get(feed, timeout=5)
            root = ET.fromstring(res.content)

            for item in root.findall(".//item"):
                title = item.findtext("title")
                link = item.findtext("link")
                source = item.findtext("source") or "不明"

                if title and link:
                    news_list.append({
                        "title": title,
                        "link": link,
                        "source": source,
                    })

                if len(news_list) >= max_items:
                    break

        except Exception as e:
            print(f"RSS取得エラー: {e}")
            continue

    return news_list
# ============================
# ニュース分類（キーワード辞書を使用）
# ============================

def classify_news_item(title: str, keywords: dict):
    """
    ニュースタイトルをキーワード辞書と照合し、
    war / peace / neutral のいずれかを返す。
    """
    title_lower = title.lower()

    # 戦時キーワード
    for category, words in keywords["war"].items():
        for w in words:
            if w.lower() in title_lower:
                return "war"

    # 平時キーワード
    for category, words in keywords["peace"].items():
        for w in words:
            if w.lower() in title_lower:
                return "peace"

    return "neutral"


def classify_news_list(news_list, keywords):
    """
    ニュースリストを分類し、
    ・戦時ニュース
    ・平時ニュース
    ・中立ニュース
    に分けて返す。
    """
    war_news = []
    peace_news = []
    neutral_news = []

    for item in news_list:
        category = classify_news_item(item["title"], keywords)

        if category == "war":
            war_news.append(item)
        elif category == "peace":
            peace_news.append(item)
            continue
        else:
            neutral_news.append(item)

    return {
        "war": war_news,
        "peace": peace_news,
        "neutral": neutral_news,
    }


def calculate_news_mode_score(classified_news):
    """
    戦時/平時ニュースの数からスコアを算出し、
    ・戦時ポイント
    ・平時ポイント
    を返す。
    """
    war_count = len(classified_news["war"])
    peace_count = len(classified_news["peace"])

    # ニュースの重み付け（調整可能）
    war_score = war_count * 10
    peace_score = peace_count * 10

    return war_score, peace_score
# ============================
# ニュースを戦時/平時モード判定に統合
# ============================

def determine_market_mode(vix_p, fgi, prev_vix, news_war_score, news_peace_score):
    """
    VIX・FGI・ニュース分類スコアを総合して
    戦時 / 平時 / 移行モード を判定する。
    """

    # ① 市場データによる基本判定
    if vix_p >= 25 or fgi <= 20:
        base_mode = "war"
    elif vix_p <= 18 and fgi >= 40:
        base_mode = "peace"
    else:
        base_mode = "transition"

    # ② ニューススコアによる補正
    #    戦時ニュースが多い → war寄り
    #    平時ニュースが多い → peace寄り
    if news_war_score - news_peace_score >= 10:
        news_mode = "war"
    elif news_peace_score - news_war_score >= 10:
        news_mode = "peace"
    else:
        news_mode = "neutral"

    # ③ 総合判定
    if base_mode == "war" or news_mode == "war":
        mode = "war"
    elif base_mode == "peace" and news_mode != "war":
        mode = "peace"
    else:
        mode = "transition"

    # ④ タイトル（既存ロジックを踏襲）
    if mode == "war":
        mode_title = "🚨戦時モード：総合反転スコア"
    elif mode == "peace":
        mode_title = "🍀平時モード：トレンドスコア"
    else:
        if vix_p >= 20 and prev_vix < 20:
            mode_title = "⚠️移行モード：警戒開始"
        elif vix_p < 20 and prev_vix >= 20:
            mode_title = "🔄移行モード：沈静化の兆し"
        else:
            mode_title = "⚠️移行モード：警戒継続"

    return mode, mode_title


# ============================
# Copilot’s View をニュース内容で強化
# ============================

def generate_copilot_view_with_news(mode, classified_news):
    """
    戦時/平時ニュースの内容を踏まえて
    Copilot’s View をより“本物のアナリスト”に近づける。
    """

    war_count = len(classified_news["war"])
    peace_count = len(classified_news["peace"])

    if mode == "war":
        if war_count >= 3:
            return (
                "地政学リスクが市場心理を強く圧迫しています。"
                "複数の戦時ニュースが同時に発生しており、"
                "反発局面は限定的となる可能性が高いです。"
            )
        else:
            return (
                "市場は警戒感を維持していますが、"
                "戦時ニュースは限定的で、過度な悲観は不要です。"
            )

    elif mode == "peace":
        if peace_count >= 3:
            return (
                "停戦協議や緊張緩和の報道が相次ぎ、"
                "投資家心理は改善傾向です。"
                "金利・コモディティも安定し、上昇トレンドが持続しやすい環境です。"
            )
        else:
            return (
                "市場は落ち着きを取り戻しつつありますが、"
                "平時ニュースはまだ限定的です。"
                "慎重な押し目買いが機能しやすい局面です。"
            )

    else:  # 移行モード
        return (
            "市場は方向感を探る展開です。"
            "戦時・平時ニュースが混在しており、"
            "短期的には上下に振れやすい相場が続きそうです。"
        )
# ============================
# メッセージ構築（ニュース統合版）
# ============================
def build_message(d):
    prev_data = load_prev_data()
    vix_p = d.get("vix_p") or 0
    prev_vix = prev_data.get("vix_p") or 0
    fgi = d.get("fgi_score") or 50

    # ----------------------------
    # ① RSSニュース取得
    # ----------------------------
    raw_news = fetch_rss_news(max_items=15)

    # ----------------------------
    # ② ニュース分類（戦時/平時/中立）
    # ----------------------------
    classified = classify_news_list(raw_news, keywords)

    # ----------------------------
    # ③ ニューススコア算出
    # ----------------------------
    news_war_score, news_peace_score = calculate_news_mode_score(classified)

    # ----------------------------
    # ④ 市場モード判定（ニュース統合版）
    # ----------------------------
    mode, mode_title = determine_market_mode(
        vix_p, fgi, prev_vix, news_war_score, news_peace_score
    )

    # ----------------------------
    # ⑤ 既存スコア計算（あなたのロジック）
    # ----------------------------
    score = 0
    max_score = 155

    if (d.get("nq_c") or 0) > 0:
        score += 25
    if (d.get("es_c") or 0) > 0:
        score += 20
    if (d.get("nk_c") or 0) > 0:
        score += 20

    if vix_p >= 30:
        score += 25
    elif vix_p >= 25:
        score += 15
    elif vix_p >= 20:
        score += 5

    if (d.get("spread") is not None) and d["spread"] < 0:
        score += 20

    if (d.get("btc_c") or 0) >= 3:
        score += 20

    scaled = min(max(int(score / max_score * 100), 0), 100)

    def fmt(p, c, dec=2):
        return f"{p:.{dec}f}（{c:+.2f}%）" if p is not None else "取得失敗"

    # ----------------------------
    # ⑥ 既存の ▼1〜6（市場データ）
    # ----------------------------
    msg = [
        f"【{d.get('date')} {mode_title}】\n",
        "▼ 1. 投資家心理 (FGI)",
        f" {get_fgi_detail(d.get('fgi_score'), d.get('fgi_prev'))}\n",

        "▼ 2. 主要指数先物 & 相対強弱",
        f" ・米 NQ100 : {fmt(d.get('nq_p'), d.get('nq_c'))}",
        f" ・米 S&P500: {fmt(d.get('es_p'), d.get('es_c'))}",
        f" ・日経平均 : {fmt(d.get('nk_p'), d.get('nk_c'))}",
        f" 💡 {get_equity_relative_comment(d.get('nk_c'), d.get('nq_c'), d.get('es_c'))}\n",

        "▼ 3. リスク指標 (VIX)",
        f" ・VIX現物: {fmt(d.get('vix_p'), d.get('vix_c'))}",
        f" ・VIX先物: {fmt(d.get('vxf_p'), d.get('vxf_c'))}",
        f" 💡 {get_vix_analysis(d.get('vix_p'), d.get('vxf_p'))}\n",

        "▼ 4. 金利・イールド",
        f" ・米10年債: {fmt(d.get('u10_p'), d.get('u10_c'))}",
        f" ・米 2年債: {fmt(d.get('u2_p'), d.get('u2_c'))}",
        (
            f" ・利回り差: {d.get('spread'):.3f}"
            if d.get("spread") is not None
            else " ・利回り差: 失敗"
        ),
        f" 💡 {get_yield_detail(d.get('spread'))}\n",

        "▼ 5. 商品 (Commodities)",
        f" ・金 (Gold): {fmt(d.get('gold_p'), d.get('gold_c'), 1)}",
        f" ・原油(WTI): {fmt(d.get('wti_p'), d.get('wti_c'))}",
        f" ・銅 (Cop) : {fmt(d.get('cop_p'), d.get('cop_c'), 3)}",
        f" 💡 {get_commodities_analysis(d.get('gold_c'), d.get('wti_c'), d.get('cop_c'))}\n",

        "▼ 6. 仮想通貨 (Crypto)",
        f" ・BTC: ${fmt(d.get('btc_p'), d.get('btc_c'), 0)}",
        f" 💡 {get_btc_comment(d.get('btc_c'))}\n",

        f"⚖️ 総合スコア：{scaled}点 / 100 （素点: {score} / {max_score}）",
        f" {'📈 打診買い検討' if scaled >= 50 else '🌑 キャッシュ保護優先'}\n",
        "--------------------------",
    ]

    # ----------------------------
    # ⑦ ニュース一覧（本物のRSSニュース）
    # ----------------------------
    msg.append("▼ 7. 主要ニュース（RSS自動取得）")

    if len(raw_news) == 0:
        msg.append("・ニュース取得失敗")
    else:
        for item in raw_news[:5]:
            msg.append(f"・{item['title']}（出所：{item['source']}）")

    msg.append("--------------------------")

    # ----------------------------
    # ⑧ Copilot’s View（ニュース反映版）
    # ----------------------------
    view = generate_copilot_view_with_news(mode, classified)
    msg.append("--- 🤖 Copilot's View ---")
    msg.append(view)

    return "\n".join(msg)


# ============================
# メイン
# ============================
def main():
    data = get_market_data()
    report = build_message(data)
    send_line(report)


if __name__ == "__main__":
    main()

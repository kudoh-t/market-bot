import os
import json
import pickle
from datetime import datetime, timezone, timedelta

import requests
from bs4 import BeautifulSoup
import feedparser  # ★ RSS用

# ============================
# 設定：環境変数
# ============================
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")

CACHE_FILE = "market_cache.pkl"

# ============================
# ニュース関連設定（平時＋戦時の完全版）
# ============================
NEWS_FEEDS = [
    "https://feeds.reuters.com/reuters/worldNews",
    "https://feeds.reuters.com/reuters/businessNews",
    "https://www.nhk.or.jp/rss/news/cat0.xml",
]

NEWS_KEYWORDS = [
    # 戦時・地政学
    "トランプ", "大統領", "関税", "イラン", "イスラエル", "ホルムズ",
    "攻撃", "ミサイル", "ウクライナ", "ロシア", "侵攻", "原油", "供給", "opec",

    # 金利・インフレ
    "金利", "利上げ", "利下げ", "長期金利", "国債", "インフレ", "デフレ",
    "物価", "pce", "コアpce", "cpi", "ppi", "frb", "金融政策", "qt", "qe",

    # 景気指標
    "gdp", "pmi", "ism", "小売売上高", "住宅着工", "失業率", "景気後退", "景気拡大",

    # 企業決算
    "決算", "ガイダンス", "予想上回る", "予想下回る", "eps", "利益率", "売上高", "業績",

    # 中国
    "中国", "不動産", "恒大", "景気刺激策", "輸出", "減速", "不況",

    # 米国政治
    "財政赤字", "政府閉鎖", "インフラ投資", "減税", "規制強化", "テック規制",
]

TRUSTED_SOURCES = [
    "reuters.com", "nhk.or.jp", "bloomberg.com", "apnews.com", "nikkei.com"
]

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
    if len(text) > 4800:
        text = text[:4800] + "\n…（一部省略）"
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
# 判定ロジック（FGI, VIX, 金利, コモディティ, BTC）
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


def get_vix_analysis(v_spot, v_3m):
    if v_spot is None or v_3m is None:
        return "⚠️VIXデータ欠損（比較不能）"
    ratio = v_spot / v_3m
    if ratio >= 1.0:
        return f"🚨異常(逆転)：比率{ratio:.2f}。現物が3ヶ月先を上回るパニック。反転間近。"
    elif ratio >= 0.9:
        return f"⚠️警戒：比率{ratio:.2f}。緊張が高まっています。"
    return f"✅正常：比率{ratio:.2f}。市場は落ち着いています。"


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
        return "🚨【スタグフレーション警戒】金・原油の同時高。"
    if gold_c > 0.5 and cop_c < -1.0:
        return "📉【景気後退シグナル】銅安・金高。"
    if cop_c > 1.5:
        return f"🏗️【銅の独歩高】{cop_c:+.1f}%の急伸。"
    if wti_c > 1.5:
        return f"🔥【エネルギー価格騰勢】原油が{wti_c:+.1f}%上昇。"
    if gold_c > 1.0:
        return f"🛡️【テールリスクヘッジ】金が{gold_c:+.1f}%上昇。"
    return "⚖️【中立】レンジ内。"


def get_btc_comment(btc_change):
    if btc_change is None:
        return "⚠️BTC取得失敗。"
    if btc_change > 3.0:
        return "🚀【リスクオン】投機資金が旺盛。"
    if btc_change < -3.0:
        return "💀【パニック】資金流出。"
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
# データ取得（Yahoo API）
# ============================
def fetch_yahoo(symbol):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
        result = res.get("chart", {}).get("result")
        if not result:
            return None, None
        meta = result[0].get("meta", {})
        p = meta.get("regularMarketPrice")
        prev = meta.get("chartPreviousClose")
        if p is None or prev is None:
            return None, None
        c = (p - prev) / prev * 100
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
def fill_with_prev(d, prev, key_price, key_change):
    """
    データ取得に失敗した場合、前回値で補完する。
    """
    if d.get(key_price) is None:
        if prev.get(key_price) not in (None, "取得失敗"):
            d[key_price] = prev[key_price]
            d[key_change] = 0.0


def get_market_data():
    d = {}
    prev = load_prev_data()

    # ============================
    # FGI（Fear & Greed Index）
    # ============================
    fgi_now, fgi_prev = fetch_fgi_raw()
    if fgi_now is None:
        # 前回値で補完
        if prev.get("fgi_score") is not None:
            fgi_now = prev.get("fgi_score")
            fgi_prev = prev.get("fgi_prev")
        else:
            fgi_now = 50
            fgi_prev = 50

    d["fgi_score"], d["fgi_prev"] = fgi_now, fgi_prev

    # ============================
    # VIX / VIX3M
    # ============================
    d["vix_p"], d["vix_c"] = fetch_yahoo("%5EVIX")
    d["v3m_p"], d["v3m_c"] = fetch_yahoo("%5EVIX3M")

    # ============================
    # 主要指数・商品・金利・BTC
    # ============================
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

    # ============================
    # 米2年債（複数候補から取得）
    # ============================
    d["u2_p"], d["u2_c"] = None, None
    for s in ["2Y=F", "^IRX", "^ZYY"]:
        p, c = fetch_yahoo(s)
        if p is not None:
            d["u2_p"], d["u2_c"] = p, c
            break

    # ============================
    # 欠損データを前回値で補完
    # ============================
    for key in ["vix", "v3m", "nq", "es", "nk", "gold", "wti", "cop", "u10", "u2", "btc"]:
        fill_with_prev(d, prev, f"{key}_p", f"{key}_c")

    # ============================
    # イールドスプレッド（10年 - 2年）
    # ============================
    d["spread"] = (
        (d.get("u10_p") - d.get("u2_p"))
        if d.get("u10_p") is not None and d.get("u2_p") is not None
        else None
    )

    # ============================
    # 日付
    # ============================
    d["date"] = datetime.now(timezone(timedelta(hours=9))).strftime("%Y.%m.%d")

    # ============================
    # キャッシュ保存
    # ============================
    save_data_cache(d)

    return d
# ============================
# ニュース取得・信頼性判定
# ============================
def is_trusted_source(link: str) -> bool:
    """
    ニュースのリンクが信頼できるドメインか判定する
    """
    if not link:
        return False
    link = link.lower()
    return any(src in link for src in TRUSTED_SOURCES)


def fetch_macro_news():
    """
    RSSフィードからニュースを取得する
    """
    items = []
    for url in NEWS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for e in feed.entries:
                items.append({
                    "title": e.get("title", "").strip(),
                    "summary": e.get("summary", "").strip(),
                    "link": e.get("link", ""),
                })
        except Exception:
            continue
    return items


def classify_news_impact(text: str) -> str:
    """
    ニュース本文から影響度を分類する
    """
    t = text.lower()

    # 地政学・戦争関連
    if any(k in t for k in ["ホルムズ", "攻撃", "ミサイル", "封鎖", "戦争"]):
        return "重大"

    # 重要経済指標
    if any(k in t for k in ["雇用統計", "cpi", "pce", "fomc", "利上げ", "利下げ"]):
        return "強い影響"

    # 景気・関税・制裁
    if any(k in t for k in ["関税", "制裁", "緊張", "景気後退"]):
        return "中程度"

    return "軽微"


def extract_relevant_news(items):
    """
    キーワードに一致するニュースを抽出し、
    信頼性の低いニュースを除外する
    """
    valid = []
    filtered = []

    for it in items:
        text = (it["title"] + " " + it["summary"]).lower()

        # キーワードに一致しないニュースは無視
        if not any(k.lower() in text for k in NEWS_KEYWORDS):
            continue

        # 信頼性チェック
        if not is_trusted_source(it["link"]):
            filtered.append(it)
            continue

        # 影響度分類
        impact = classify_news_impact(text)
        it["impact"] = impact
        valid.append(it)

    return valid, filtered
# ============================
# ニュースセクション構築
# ============================
def build_news_section(valid_news, filtered_news):
    """
    ニュース本文を LINE 通知用に整形し、
    Copilot に渡すためのサマリーも生成する
    """
    lines = []
    news_summary_for_copilot = []

    # ニュースが全くない場合
    if not valid_news and not filtered_news:
        lines.append("ニュース：本日、市場に大きな影響を与えるニュースは確認されませんでした。")
        return "\n".join(lines), "", ""

    # ----------------------------
    # 信頼できるニュース（最大5件）
    # ----------------------------
    for idx, n in enumerate(valid_news[:5], start=1):
        title = n["title"]
        impact = n.get("impact", "中程度")

        # 影響度に応じたコメント
        if impact == "重大":
            comment = "原油・金利・指数に影響しうるレベルのイベントです。"
        elif impact == "強い影響":
            comment = "セクターや指数の方向性を変えうる重要イベントです。"
        elif impact == "中程度":
            comment = "一部セクターや投資家心理に影響しうるニュースです。"
        else:
            comment = "影響は限定的ですが、継続的なフォローが必要です。"

        lines.append(f"📰 個別ニュース {idx}")
        lines.append(f"「{title}」")
        lines.append(f"→ 【{impact}】{comment}")

        # Copilot用サマリー
        news_summary_for_copilot.append(f"- {title}（影響度: {impact}）")

    # ----------------------------
    # フェイク/信頼性低ニュース
    # ----------------------------
    fake_lines = []
    for n in filtered_news[:3]:
        fake_lines.append(f"- 「{n['title']}」")

    fake_block = ""
    if fake_lines:
        fake_block = (
            "🚫 フェイク/信頼性低ニュースとして除外:\n" +
            "\n".join(fake_lines)
        )

    return "\n".join(lines), "\n".join(news_summary_for_copilot), fake_block


# ============================
# Copilot ローカル評価（ニュース用）
# ============================
def copilot_news_comment(news_summary_block: str) -> str:
    """
    ニュースの影響度を Copilot が総合評価したコメント
    """
    if not news_summary_block:
        return (
            "本日は市場に大きな影響を与えるマクロニュースは限定的で、"
            "ニュース要因によるボラティリティは小さそうです。"
        )

    text = news_summary_block

    # 重大ニュースが含まれる
    if "重大" in text:
        return (
            "地政学リスクや供給リスクなど、市場全体のセンチメントを冷やしうるニュースが含まれています。"
            "短期的なリスク回避姿勢に注意が必要です。"
        )

    # 強い影響ニュースが含まれる
    if "強い影響" in text:
        return (
            "重要な経済指標や政策関連ニュースがあり、"
            "金利やセクターのトレンドに影響を与えうる環境です。"
        )

    # それ以外
    return (
        "ニュースは複数ありますが、現時点では市場全体を大きく揺るがす決定的な材料というより、"
        "センチメントをじわじわと動かす性質のものが中心です。"
    )
# ============================
# Copilot 総合コメント（1〜7統合）
# ============================
def copilot_total_comment(d, news_summary_block: str) -> str:
    """
    FGI、VIX、金利、コモディティ、BTC、ニュースを統合した
    Copilot の総合マクロコメント
    """
    fgi = d.get("fgi_score") or 50
    vix = d.get("vix_p") or 0
    spread = d.get("spread")
    gold_c = d.get("gold_c") or 0
    wti_c = d.get("wti_c") or 0
    btc_c = d.get("btc_c") or 0

    # ----------------------------
    # ① 市場全体のトーン
    # ----------------------------
    if fgi <= 25 or vix >= 25:
        tone = "全体としては警戒感が強く、リスク回避姿勢が優勢な地合いです。"
    elif fgi >= 60 and vix <= 15:
        tone = "全体としてはリスクオンのムードが強く、押し目は拾われやすい環境です。"
    else:
        tone = "全体としては中立〜ややリスクオン寄りのバランス型の地合いです。"

    # ----------------------------
    # ② 金利・イールド
    # ----------------------------
    if spread is not None and spread < 0:
        y_comment = "逆イールドが継続しており、中長期的な景気後退リスクは依然として意識されます。"
    elif spread is not None and spread > 0.7:
        y_comment = "イールドカーブの急拡大が見られ、金利上昇によるバリュエーション調整リスクに注意が必要です。"
    else:
        y_comment = "金利構造は大きな歪みはなく、金利要因は中立〜やや追い風といえます。"

    # ----------------------------
    # ③ コモディティ
    # ----------------------------
    if gold_c > 0.5 and wti_c > 1.0:
        c_comment = "金と原油が同時に上昇しており、スタグフレーション的なインフレ懸念が意識されやすい局面です。"
    elif gold_c > 0.5:
        c_comment = "金価格の上昇が続いており、テールリスクや不確実性に対するヘッジ需要が高まっています。"
    elif wti_c > 1.0:
        c_comment = "原油価格の上昇が続いており、エネルギーコストを通じたインフレ圧力に注意が必要です。"
    else:
        c_comment = "コモディティはおおむねレンジ内で推移しており、マクロ面での決定的なシグナルは限定的です。"

    # ----------------------------
    # ④ BTC
    # ----------------------------
    if btc_c >= 3:
        b_comment = "BTCの上昇は、投機的なリスク許容度がまだ失われていないことを示しています。"
    elif btc_c <= -3:
        b_comment = "BTCの下落は、リスク資産からの資金引き上げが進んでいる可能性を示唆します。"
    else:
        b_comment = "BTCは大きなトレンド変化は見られず、リスク許容度は概ね維持されています。"

    # ----------------------------
    # ⑤ ニュース要因
    # ----------------------------
    if "重大" in news_summary_block or "強い影響" in news_summary_block:
        n_comment = (
            "マクロニュース面では、地政学や重要指標・政策発言が相場の変動要因となりやすい環境です。"
        )
    elif news_summary_block:
        n_comment = (
            "マクロニュースは複数あるものの、現時点では決定的なトレンド転換要因というより、"
            "センチメントをじわりと動かす材料が中心です。"
        )
    else:
        n_comment = (
            "ニュース要因は限定的で、当面はテクニカルや需給要因が相場を主導しやすい状況です。"
        )

    # ----------------------------
    # 最終統合コメント
    # ----------------------------
    return (
        f"{tone}\n"
        f"{y_comment}\n"
        f"{c_comment}\n"
        f"{b_comment}\n"
        f"{n_comment}"
    )
# ============================
# メッセージ構築（後半）
# ============================
def build_message(d, news_valid, news_filtered):
    prev_data = load_prev_data()
    vix_p = d.get("vix_p") or 0
    prev_vix = prev_data.get("vix_p") or 0
    fgi = d.get("fgi_score") or 50

    # ----------------------------
    # モード判定
    # ----------------------------
    if vix_p >= 25 or fgi <= 20:
        mode_title = "🚨戦時モード：総合反転スコア"
    elif vix_p <= 18 and fgi >= 40:
        mode_title = "🍀平時モード：トレンドスコア"
    else:
        if vix_p >= 20 and prev_vix < 20:
            mode_title = "⚠️移行モード：警戒開始"
        elif vix_p < 20 and prev_vix >= 20:
            mode_title = "🔄移行モード：沈静化の兆し"
        else:
            mode_title = "⚠️移行モード：警戒継続"

    # ----------------------------
    # スコア計算
    # ----------------------------
    score = 0
    max_score = 155

    if (d.get("nq_c") or 0) > 0: score += 25
    if (d.get("es_c") or 0) > 0: score += 20
    if (d.get("nk_c") or 0) > 0: score += 20

    if vix_p >= 30: score += 25
    elif vix_p >= 25: score += 15
    elif vix_p >= 20: score += 5

    if (d.get("spread") is not None) and d["spread"] < 0:
        score += 20

    if (d.get("btc_c") or 0) >= 3:
        score += 20

    scaled = min(max(int(score / max_score * 100), 0), 100)

    # ----------------------------
    # 表示フォーマット
    # ----------------------------
    def fmt(p, c, dec=2):
        return f"{p:.{dec}f}（{c:+.2f}%）" if p is not None else "取得失敗"

    # ----------------------------
    # ニュースセクション
    # ----------------------------
    news_block, news_summary_block, fake_block = build_news_section(news_valid, news_filtered)
    news_copilot_view = copilot_news_comment(news_summary_block)
    total_copilot_view = copilot_total_comment(d, news_summary_block)

    # ----------------------------
    # メッセージ本文
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

        "▼ 3. リスク指標 (VIX/VIX3M)",
        f" ・VIX現物: {fmt(d.get('vix_p'), d.get('vix_c'))}",
        f" ・VIX 3M : {fmt(d.get('v3m_p'), d.get('v3m_c'))}",
        f" 💡 {get_vix_analysis(d.get('vix_p'), d.get('v3m_p'))}\n",

        "▼ 4. 金利・イールド",
        f" ・米10年債: {fmt(d.get('u10_p'), d.get('u10_c'))}",
        f" ・米 2年債: {fmt(d.get('u2_p'), d.get('u2_c'))}",
        (f" ・利回り差: {d.get('spread'):.3f}" if d.get("spread") is not None else " ・利回り差: 失敗"),
        f" 💡 {get_yield_detail(d.get('spread'))}\n",

        "▼ 5. 商品 (Commodities)",
        f" ・金 (Gold): {fmt(d.get('gold_p'), d.get('gold_c'), 1)}",
        f" ・原油(WTI): {fmt(d.get('wti_p'), d.get('wti_c'))}",
        f" ・銅 (Cop) : {fmt(d.get('cop_p'), d.get('cop_c'), 3)}",
        f" 💡 {get_commodities_analysis(d.get('gold_c'), d.get('wti_c'), d.get('cop_c'))}\n",

        "▼ 6. 仮想通貨 (Crypto)",
        f" ・BTC: ${fmt(d.get('btc_p'), d.get('btc_c'), 0)}",
        f" 💡 {get_btc_comment(d.get('btc_c'))}\n",

        "▼ 7. マクロニュース（個別ニュース＋総合コメント）",
        news_block,
        "",
        "🤖 Copilotのマクロニュース総合コメント",
        f" {news_copilot_view}",
    ]

    if fake_block:
        msg.append("")
        msg.append(fake_block)

    msg.extend([
        "\n▼ 8. Copilot総合コメント（1〜7すべてを統合）",
        total_copilot_view,
        "",
        f"⚖️ 総合スコア：{scaled}点 / 100 （素点: {score} / {max_score}）",
        f" {'📈 打診買い検討' if scaled >= 50 else '🌑 キャッシュ保護優先'}",
        "--------------------------",
    ])

    return "\n".join(msg)
# ============================
# メイン処理
# ============================
def main():
    # 1. 市場データ取得
    data = get_market_data()

    # 2. ニュース取得
    all_news = fetch_macro_news()

    # 3. ニュース分類（有効ニュース＋フェイク除外ニュース）
    news_valid, news_filtered = extract_relevant_news(all_news)

    # 4. LINE通知メッセージ構築
    report = build_message(data, news_valid, news_filtered)

    # 5. LINEへ送信
    send_line(report)


# ============================
# エントリーポイント
# ============================
if __name__ == "__main__":
    main()
# ============================
# 補完パート（例外処理・安全ガード）
# ============================

def safe_get(d: dict, key: str, default=None):
    """
    辞書から安全に値を取得するための補助関数。
    """
    try:
        return d.get(key, default)
    except Exception:
        return default


def safe_float(v, default=None):
    """
    数値変換の安全版。
    """
    try:
        return float(v)
    except Exception:
        return default


def safe_percent_change(current, previous):
    """
    前日比計算の安全版。
    """
    try:
        if current is None or previous is None:
            return None
        return (current - previous) / previous * 100
    except Exception:
        return None


# ============================
# デバッグ用（必要に応じて使用）
# ============================
def debug_print_data(d):
    """
    デバッグ用に市場データを整形して出力する。
    本番運用では呼び出さない。
    """
    print("\n===== DEBUG: MARKET DATA =====")
    for k, v in d.items():
        print(f"{k}: {v}")
    print("===== END DEBUG =====\n")


# ============================
# 将来の拡張用のプレースホルダー
# ============================
def future_extension_hook():
    """
    将来の機能追加のためのフック。
    例：AI予測、セクター別分析、需給分析など。
    """
    pass
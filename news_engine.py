import feedparser
MAX_TOTAL_SCORE = 125

# ============================================
# RSS FEEDS
# ============================================
RSS_FEEDS = [
    # Reuters（最重要）
    "https://feeds.reuters.com/reuters/topNews",
    "https://feeds.reuters.com/Reuters/worldNews",

    # MarketWatch（マーケット速報）
    "https://feeds.marketwatch.com/marketwatch/marketpulse/",

    # BBC（世界ニュース）
    "http://feeds.bbci.co.uk/news/world/rss.xml",

    # CNN（国際ニュース）
    "http://rss.cnn.com/rss/edition.rss",

    # AP News（速報性が高い）
    "https://apnews.com/rss"
]


# ============================================
# 信頼スコア辞書（フェイクニュース排除）
# ============================================
NEWS_SOURCE_SCORE = {
    "reuters": 95,
    "marketwatch": 85,
    "bloomberg": 95,
    "apnews": 90,
    "bbc": 90,
    "cnn": 80,
    "foxnews": 70,
    "yahoo": 70,
    "unknown": 50
}
def get_news_importance(title):
    title_lower = title.lower()

    geo_hit = any(k.lower() in title_lower for k in GEOPOLITICS_KEYWORDS)
    mon_hit = any(k.lower() in title_lower for k in MONETARY_KEYWORDS)

    if geo_hit and mon_hit:
        return 30  # 両方ヒットは最重要
    elif geo_hit:
        return 20  # 地政学
    elif mon_hit:
        return 20  # 金融政策
    else:
        return 0   # その他

def get_source_name(link):
    link = link.lower()
    for source in NEWS_SOURCE_SCORE.keys():
        if source in link:
            return source
    return "unknown"

def get_source_score(link):
    link = link.lower()
    for source, score in NEWS_SOURCE_SCORE.items():
        if source in link:
            return score
    return NEWS_SOURCE_SCORE["unknown"]

# ============================================
# ニュース取得（信頼フィルタ付き）
# ============================================
def fetch_news(max_items=20):
    news = []

    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                title = entry.title
                link = entry.link
                source = get_source_name(link)
                score = get_source_score(link)   # ★ 追加
                importance = get_news_importance(title)  # ★追加
                news.append({
                    "title": title,
                    "link": link,
                    "source": source,
                    "score": score,
                    "importance": importance,            # ★追加
                    "total_score": score + importance,    # ★追加
                    "normalized_score": normalized
            })
        except Exception:
            continue

    # ▼ 重複削除 + ? を含む変なニュース除外
    seen = set()
    unique_news = []
    for n in news:
        title = n["title"]

        if title in seen:
            continue

        if "?" in title:
            continue

        unique_news.append(n)
        seen.add(title)

    # ▼ ★ スコア順に並べる（高い順）
    #unique_news.sort(key=lambda x: get_source_score(x["link"]), reverse=True)
    #unique_news.sort(key=lambda x: x["total_score"], reverse=True)
    unique_news.sort(key=lambda x: x["normalized_score"], reverse=True)

    # ▼ 信頼スコアでフィルタ（70点以上のみ）
    filtered = []
    for n in unique_news:
        score = get_source_score(n["link"])
        if score >= 70:
            filtered.append(n)

    # ▼ 件数制限
    return filtered[:max_items]


# ============================================
# キーワード辞書（日本語＋英語）
# ============================================
GEOPOLITICS_KEYWORDS = [
    # 日本語
    "戦闘","攻撃","停戦","軍事","ミサイル","侵攻","紛争",
    "中東","ガザ","イスラエル","イラン","ロシア","ウクライナ",
    "制裁","地政学","軍事衝突","核","防衛","報復",

    # 英語
    "war", "conflict", "military", "missile", "attack", "strike",
    "invasion", "geopolitics", "sanction", "tension", "border clash",
    "middle east", "israel", "gaza", "iran", "russia", "ukraine",
    "airstrike", "bombing", "ceasefire"
]

MONETARY_KEYWORDS = [
    # 日本語
    "利上げ","利下げ","金利据え置き","FOMC","FRB","ECB","日銀",
    "金融政策","量的緩和","QT","インフレ","CPI","PCE","失業率",
    "景気後退","景気減速","タカ派","ハト派",

    # 英語
    "rate hike", "rate cut", "interest rate", "inflation", "cpi",
    "pce", "jobs report", "unemployment", "fed", "ecb", "boj",
    "monetary policy", "hawkish", "dovish", "recession", "slowdown",
    "quantitative tightening", "quantitative easing"
]

# ============================================
# ニュース分類
# ============================================
def classify_news_list(news_list):
    result = {"categories": {"geopolitics": [], "monetary": [], "other": []}}

    for n in news_list:
        title = n["title"].lower()

        geo_hit = any(k.lower() in title for k in GEOPOLITICS_KEYWORDS)
        mon_hit = any(k.lower() in title for k in MONETARY_KEYWORDS)

        if geo_hit and not mon_hit:
            result["categories"]["geopolitics"].append(n)
        elif mon_hit and not geo_hit:
            result["categories"]["monetary"].append(n)
        elif geo_hit and mon_hit:
            result["categories"]["geopolitics"].append(n)
        else:
            result["categories"]["other"].append(n)

    return result

# ============================================
# ニューススコア
# ============================================
def score_news(classified):
    war_score = len(classified["categories"]["geopolitics"])
    peace_score = len(classified["categories"]["monetary"])
    return war_score, peace_score

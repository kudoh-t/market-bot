import feedparser

# ============================================
# RSS FEEDS
# ============================================
RSS_FEEDS = [
    "https://feeds.reuters.com/reuters/topNews",
    "https://feeds.reuters.com/Reuters/worldNews",
    "https://feeds.marketwatch.com/marketwatch/topstories/"
]

# ============================================
# ニュース取得
# ============================================
def fetch_news(max_items=20):
    news = []

    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                title = entry.title
                link = entry.link
                news.append({"title": title, "link": link})
        except Exception:
            continue

    # 重複削除
    seen = set()
    unique_news = []
    for n in news:
        if n["title"] not in seen:
            unique_news.append(n)
            seen.add(n["title"])

    return unique_news[:max_items]

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
        title = n["title"].lower()  # 英語判定用に小文字化

        geo_hit = any(k.lower() in title for k in GEOPOLITICS_KEYWORDS)
        mon_hit = any(k.lower() in title for k in MONETARY_KEYWORDS)

        if geo_hit and not mon_hit:
            result["categories"]["geopolitics"].append(n)
        elif mon_hit and not geo_hit:
            result["categories"]["monetary"].append(n)
        elif geo_hit and mon_hit:
            # 両方ヒット → 地政学優先
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

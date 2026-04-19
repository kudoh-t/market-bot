import feedparser

# スコアの最大値（正規化用）
MAX_TOTAL_SCORE = 125

# ============================================
# RSS FEEDS（海外＋日本語ニュース統合版）
# ============================================
RSS_FEEDS = [
    # --- 海外ニュース ---
    "https://feeds.reuters.com/reuters/topNews",
    "https://feeds.reuters.com/Reuters/worldNews",
    "https://feeds.marketwatch.com/marketwatch/marketpulse/",
    "http://feeds.bbci.co.uk/news/world/rss.xml",
    "http://rss.cnn.com/rss/edition.rss",
    "https://apnews.com/rss",
    "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839069",

    # --- 日本語ニュース（追加） ---
    "https://jp.reuters.com/rssFeed/topNews",
    "https://jp.reuters.com/rssFeed/worldNews",
    "https://jp.reuters.com/rssFeed/businessNews",

    "https://news.yahoo.co.jp/rss/topics/top-picks.xml",
    "https://news.yahoo.co.jp/rss/topics/business.xml",
    "https://news.yahoo.co.jp/rss/topics/it.xml",
    "https://news.yahoo.co.jp/rss/topics/economy.xml",

    "https://www3.nhk.or.jp/rss/news/cat0.xml",
    "https://www3.nhk.or.jp/rss/news/cat5.xml",

    "https://www.nikkei.com/rss/news",
]

# 信頼スコア辞書
NEWS_SOURCE_SCORE = {
    "reuters": 95,
    "marketwatch": 85,
    "bloomberg": 95,
    "apnews": 90,
    "bbc": 90,
    "cnn": 80,
    "cnbc": 85,
    "nikkei": 90,
    "yahoo": 85,
    "nhk": 90,
    "unknown": 50
}

# ============================================
# キーワード辞書（日本語ニュース最適化）
# ============================================
GEOPOLITICS_KEYWORDS = [
    "戦闘","攻撃","停戦","軍事","ミサイル","侵攻","紛争","中東","ガザ","イスラエル",
    "イラン","ロシア","ウクライナ","制裁","核","防衛","報復","北朝鮮","台湾海峡",
    "紅海","ホルムズ","自衛隊","領空","領海","衝突",
    "war","conflict","military","missile","attack","strike","invasion",
    "geopolitics","sanction","airstrike","border","hostage","houthi",
    "red sea","hormuz","taiwan strait","navy"
]

MONETARY_KEYWORDS = [
    "利上げ","利下げ","金利","FOMC","FRB","ECB","日銀","金融政策","量的緩和","QT",
    "インフレ","デフレ","CPI","PCE","失業率","景気後退","景気減速","タカ派","ハト派",
    "国債","長期金利","短期金利","為替","円安","円高",
    "rate hike","rate cut","interest rate","inflation","cpi","pce","fed",
    "monetary policy","recession","treasury","bond yield","ecb","boj"
]

INDUSTRY_KEYWORDS = [
    "決算","上方修正","下方修正","増益","減益","増配","減配","設備投資","半導体",
    "人工知能","生成AI","DX","受注","GDP","PMI","製造業","サービス業","輸出","輸入",
    "企業","市場","株価","業績","経済","物価","消費","自動車","電機","通信","IT",
    "新製品","新サービス","投資","資金調達","上場","IPO",
    "earnings","results","guidance","upside","dividend","semiconductor",
    "ai","nvidia","tsmc","investment","orders","gdp","pmi","manufacturing",
    "tech","industry","market","company"
]

# ============================================
# ユーティリティ
# ============================================
def get_source_name(link):
    link = link.lower()
    for source in NEWS_SOURCE_SCORE.keys():
        if source in link:
            return source
    return "unknown"

def get_source_score(link):
    return NEWS_SOURCE_SCORE.get(get_source_name(link), 50)

def get_news_importance(title):
    t = title.lower()
    geo = any(k.lower() in t for k in GEOPOLITICS_KEYWORDS)
    mon = any(k.lower() in t for k in MONETARY_KEYWORDS)
    ind = any(k.lower() in t for k in INDUSTRY_KEYWORDS)

    score = 0
    if geo: score += 20
    if mon: score += 20
    if ind: score += 30
    return min(30, score)

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
                s_score = get_source_score(link)
                importance = get_news_importance(title)
                total = s_score + importance

                news.append({
                    "title": title,
                    "link": link,
                    "source": get_source_name(link),
                    "score": s_score,
                    "importance": importance,
                    "normalized_score": int((total / MAX_TOTAL_SCORE) * 100)
                })
        except:
            continue

    # タイトル重複削除
    seen = set()
    unique = []
    for n in news:
        if n["title"] not in seen and "?" not in n["title"]:
            unique.append(n)
            seen.add(n["title"])

    unique.sort(key=lambda x: x["normalized_score"], reverse=True)
    return [n for n in unique if n["score"] >= 65][:max_items]

# ============================================
# ニュース分類（優先度方式）
# ============================================
def classify_news_list(news_list):
    result = {"categories": {"geopolitics": [], "monetary": [], "other": []}}

    for n in news_list:
        title = n["title"]

        geo_hit = any(k in title for k in GEOPOLITICS_KEYWORDS)
        mon_hit = any(k in title for k in MONETARY_KEYWORDS)
        ind_hit = any(k in title for k in INDUSTRY_KEYWORDS)

        if geo_hit:
            result["categories"]["geopolitics"].append(n)
        elif mon_hit:
            result["categories"]["monetary"].append(n)
        elif ind_hit:
            result["categories"]["other"].append(n)
        else:
            result["categories"]["other"].append(n)

    return result

# ============================================
# カテゴリ間の重複排除（URLベース）
# ============================================
def remove_cross_category_duplicates(classified):
    geo_links = {n["link"] for n in classified["categories"]["geopolitics"]}

    classified["categories"]["monetary"] = [
        n for n in classified["categories"]["monetary"]
        if n["link"] not in geo_links
    ]

    classified["categories"]["other"] = [
        n for n in classified["categories"]["other"]
        if n["link"] not in geo_links
    ]

    return classified

# ============================================
# スコアリング
# ============================================
def score_news(classified):
    def get_cat_sum(cat):
        return sum(n["normalized_score"] for n in classified["categories"][cat])

    war_sum = get_cat_sum("geopolitics")
    mon_sum = get_cat_sum("monetary")
    ind_sum = get_cat_sum("other")

    war_score = int(war_sum * 0.6)
    peace_score = int(mon_sum + ind_sum * 1.2)

    return war_score, peace_score

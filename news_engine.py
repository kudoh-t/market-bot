import feedparser

# スコアの最大値（正規化用）
MAX_TOTAL_SCORE = 125

# ============================================
# RSS FEEDS (経済・テックを強化)
# ============================================
RSS_FEEDS = [
    "https://feeds.reuters.com/reuters/topNews",
    "https://feeds.reuters.com/Reuters/worldNews",
    "https://feeds.marketwatch.com/marketwatch/marketpulse/",
    "http://feeds.bbci.co.uk/news/world/rss.xml",
    "http://rss.cnn.com/rss/edition.rss",
    "https://apnews.com/rss",
    # 産業・テック・経済を強化するために追加
    "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839069" # CNBC Finance
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
    "foxnews": 70,
    "yahoo": 70,
    "unknown": 50
}

# ============================================
# キーワード辞書（実体経済・テックを新設）
# ============================================
GEOPOLITICS_KEYWORDS = [
    "戦闘","攻撃","停戦","軍事","ミサイル","侵攻","紛争","中東","ガザ","イスラエル",
    "イラン","ロシア","ウクライナ","制裁","地政学","核","防衛","報復","war", "conflict", 
    "military", "missile", "attack", "strike", "invasion", "geopolitics", "sanction"
]

MONETARY_KEYWORDS = [
    "利上げ","利下げ","金利","FOMC","FRB","ECB","日銀","金融政策","量的緩和","QT","インフレ",
    "CPI","PCE","失業率","景気後退","景気減速","タカ派","ハト派","rate hike", "rate cut", 
    "interest rate", "inflation", "cpi", "fed", "monetary policy", "recession"
]

INDUSTRY_KEYWORDS = [
    "決算","上方修正","増益","増配","設備投資","半導体","人工知能","生成AI","DX",
    "先行指標","受注","GDP","PMI","earnings", "results", "guidance", "upside", "dividend", 
    "semiconductor", "ai", "nvidia", "tsmc", "investment", "orders", "gdp", "pmi"
]

# ============================================
# ユーティリティ
# ============================================
def get_source_name(link):
    link = link.lower()
    for source in NEWS_SOURCE_SCORE.keys():
        if source in link: return source
    return "unknown"

def get_source_score(link):
    source = get_source_name(link)
    return NEWS_SOURCE_SCORE.get(source, 50)

def get_news_importance(title):
    title_lower = title.lower()
    geo = any(k.lower() in title_lower for k in GEOPOLITICS_KEYWORDS)
    mon = any(k.lower() in title_lower for k in MONETARY_KEYWORDS)
    ind = any(k.lower() in title_lower for k in INDUSTRY_KEYWORDS)

    score = 0
    if geo: score += 20
    if mon: score += 20
    if ind: score += 25 # 実体経済ニュースをやや重視
    return min(30, score)

# ============================================
# ニュース取得・分類・スコアリング
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
                s_score = get_source_score(link)
                importance = get_news_importance(title)
                
                total = s_score + importance
                news.append({
                    "title": title,
                    "link": link,
                    "source": source,
                    "score": s_score,
                    "importance": importance,
                    "normalized_score": int((total / MAX_TOTAL_SCORE) * 100)
                })
        except: continue

    # 重複削除とクエリニュース除外
    seen = set()
    unique_news = []
    for n in news:
        if n["title"] not in seen and "?" not in n["title"]:
            unique_news.append(n)
            seen.add(n["title"])

    # スコア順ソートとフィルタ
    unique_news.sort(key=lambda x: x["normalized_score"], reverse=True)
    return [n for n in unique_news if n["score"] >= 70][:max_items]

def classify_news_list(news_list):
    result = {"categories": {"geopolitics": [], "monetary": [], "other": []}}

    for n in news_list:
        title = n["title"]

        geo_hit = any(k in title for k in GEOPOLITICS_KEYWORDS)
        mon_hit = any(k in title for k in MONETARY_KEYWORDS)

        if geo_hit and not mon_hit:
            result["categories"]["geopolitics"].append(n)
        elif mon_hit and not geo_hit:
            result["categories"]["monetary"].append(n)
        elif geo_hit and mon_hit:
            result["categories"]["geopolitics"].append(n)
        else:
            result["categories"]["other"].append(n)

    # --- カテゴリ間の重複排除（地政学を最優先） ---
    geo_titles = {n["title"] for n in result["categories"]["geopolitics"]}

    result["categories"]["monetary"] = [
        n for n in result["categories"]["monetary"]
        if n["title"] not in geo_titles
    ]

    result["categories"]["other"] = [
        n for n in result["categories"]["other"]
        if n["title"] not in geo_titles
    ]

    return result


def score_news(classified):
    """
    ニュースの重要度合計に基づき、War(弱気)とPeace(強気)のスコアを算出。
    Industryの結果をPeace側に加算し、地政学の重みを調整する。
    """
    def get_cat_sum(cat):
        return sum(n["normalized_score"] for n in classified["categories"][cat])

    war_sum = get_cat_sum("geopolitics")
    mon_sum = get_cat_sum("monetary")
    ind_sum = get_cat_sum("industry")

    # 地政学のノイズを 0.6倍に抑制 (弱気バイアスの緩和)
    # 金融政策と産業ニュースを合算して強気スコアとする
    war_score = int(war_sum * 0.6)
    peace_score = int((mon_sum * 1.0) + (ind_sum * 1.2)) # 実体経済を1.2倍で評価

    return war_score, peace_score
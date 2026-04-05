import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET

# ============================
# ニュース出所の信頼度スコア（変更なし）
# ============================
NEWS_SOURCE_SCORE = {
    "ロイター": 95,
    "Reuters": 95,
    "Bloomberg": 95,
    "BBC": 90,
    "AP": 90,
    "AFP": 90,
    "共同通信": 85,
    "時事通信": 85,
    "日経新聞": 90,
    "読売新聞": 80,
    "朝日新聞": 80,
    "毎日新聞": 80,
    "不明": 50,
}

# ============================
# RSSフィード一覧（変更なし）
# ============================
NEWS_FEEDS = [
    "https://news.yahoo.co.jp/rss/topics/top-picks.xml",
    "https://news.yahoo.co.jp/rss/topics/world.xml",
    "https://news.yahoo.co.jp/rss/topics/business.xml",
]

# ============================
# Yahooニュース記事ページから出所を抽出（変更なし）
# ============================
def extract_source_from_article(url):
    try:
        html = requests.get(url, timeout=5).text
        soup = BeautifulSoup(html, "html.parser")

        # Yahooニュースの配信元はこのCSSクラスに入っている
        src_el = soup.select_one("span.sc-fzqARJ, span.sc-dRFtgE, span.sc-iGgWBj")
        if src_el:
            return src_el.text.strip()

    except Exception as e:
        print(f"出所抽出エラー: {e}")

    return "不明"

# ============================
# RSSニュース取得（★修正：重複と関係ないニュースを排除）
# ============================
def fetch_rss_news(max_items=15):
    news_list = []
    seen_links = set()  # 重複URLチェック用

    for feed in NEWS_FEEDS:
        try:
            res = requests.get(feed, timeout=5)
            root = ET.fromstring(res.content)

            for item in root.findall(".//item"):
                title = item.findtext("title")
                link = item.findtext("link")

                if title and link:
                    # 1. すでに取得済みのリンク（重複）ならスキップ
                    if link in seen_links:
                        continue
                    
                    # 2. 投資に関係ないカテゴリ（other）ならスキップ
                    if classify_category(title) == "other":
                        continue

                    source = extract_source_from_article(link)

                    news_list.append({
                        "title": title,
                        "link": link,
                        "source": source,
                    })
                    
                    # 取得済みリストにリンクを記録
                    seen_links.add(link)

                if len(news_list) >= max_items:
                    break

        except Exception as e:
            print(f"RSS取得エラー: {e}")
            continue

    return news_list

# ============================
# ニュースカテゴリ分類（変更なし）
# ============================
CATEGORY_KEYWORDS = {
    "geopolitics": ["イラン", "イスラエル", "ウクライナ", "ロシア", "北朝鮮", "軍事", "攻撃", "報復", "ミサイル"],
    "monetary": ["FRB", "利下げ", "利上げ", "金利", "インフレ", "CPI", "PCE", "FOMC"],
    "commodity": ["原油", "WTI", "OPEC", "金", "銅", "天然ガス"],
    "equity": ["S&P", "NASDAQ", "日経", "決算", "株", "企業"],
}

def classify_category(title):
    title_lower = title.lower()

    for cat, words in CATEGORY_KEYWORDS.items():
        for w in words:
            if w.lower() in title_lower:
                return cat

    return "other"

# ============================
# 戦時 / 平時 ニュース分類（変更なし）
# ============================
WAR_KEYWORDS = ["攻撃", "軍事", "報復", "ミサイル", "戦闘", "紛争", "衝突"]
PEACE_KEYWORDS = ["停戦", "協議", "合意", "和平", "緊張緩和"]

def classify_war_peace(title):
    t = title.lower()

    for w in WAR_KEYWORDS:
        if w.lower() in t:
            return "war"

    for w in PEACE_KEYWORDS:
        if w.lower() in t:
            return "peace"

    return "neutral"

# ============================
# ニュースリストを分類（変更なし）
# ============================
def classify_news_list(news_list):
    classified = {
        "war": [],
        "peace": [],
        "neutral": [],
        "categories": {
            "geopolitics": [],
            "monetary": [],
            "commodity": [],
            "equity": [],
            "other": [],
        }
    }

    for item in news_list:
        # 戦時/平時分類
        wp = classify_war_peace(item["title"])
        classified[wp].append(item)

        # カテゴリ分類
        cat = classify_category(item["title"])
        classified["categories"][cat].append(item)

    return classified

# ============================
# ニューススコア（変更なし）
# ============================
def calculate_news_mode_score(classified_news):
    war_score = 0
    peace_score = 0

    for item in classified_news["war"]:
        src = item["source"]
        base = NEWS_SOURCE_SCORE.get(src, 50)
        war_score += base / 10

    for item in classified_news["peace"]:
        src = item["source"]
        base = NEWS_SOURCE_SCORE.get(src, 50)
        peace_score += base / 10

    return int(war_score), int(peace_score)
import os
from market_data import get_market_data
from analysis import analyze_market
from message_builder import build_message
from news_engine import (
    fetch_rss_news,
    classify_news_list,
    calculate_news_mode_score
)
from send_line import send_line   # ← send_line が別ファイルなら修正

def main():
    # ① 市場データ取得
    market = get_market_data()

    # ② ニュース取得
    news_list = fetch_rss_news()

    # ③ ニュース分類
    classified_news = classify_news_list(news_list)

    # ④ ニューススコア（戦時/平時）
    war_score, peace_score = calculate_news_mode_score(classified_news)

    # ⑤ 市場分析
    analysis_result = analyze_market(market, classified_news, war_score, peace_score)

    # ⑥ LINEメッセージ生成
    report = build_message(market, classified_news, analysis_result)

    # ⑦ LINE送信
    send_line(report)

if __name__ == "__main__":
    main()
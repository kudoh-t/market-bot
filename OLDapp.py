import requests
import json
import os

# ============================
# 設定（環境変数から取得）
# ============================
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")

def send_line(text: str):
    if not LINE_ACCESS_TOKEN or not LINE_USER_ID:
        print("LINE設定が不足しているため、標準出力のみ行います。")
        print(text)
        return

    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_ACCESS_TOKEN}",
    }
    body = {
        "to": LINE_USER_ID,
        "messages": [{"type": "text", "text": text}],
    }
    response = requests.post(url, headers=headers, data=json.dumps(body))
    if response.status_code == 200:
        print("LINE送信成功")
    else:
        print(f"LINE送信失敗: {response.status_code} {response.text}")

# ============================
# 市場データ取得
# ============================

def get_json(url: str):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        return response.json()
    except Exception as e:
        print(f"取得失敗: {url} - {e}")
        return None

def fetch_yahoo(symbol: str):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    data = get_json(url)
    if data and "chart" in data and data["chart"]["result"]:
        meta = data["chart"]["result"][0]["meta"]
        price = meta.get("regularMarketPrice", 0.0)
        prev = meta.get("chartPreviousClose", 0.0)
        change = ((price - prev) / prev * 100) if prev != 0 else 0.0
        return price, change
    return 0.0, 0.0

def get_market_data():
    # 各種シンボル取得
    gold_p, gold_c = fetch_yahoo("GC=F")
    wti_p, wti_c = fetch_yahoo("CL=F")
    vix_p, vix_c = fetch_yahoo("%5EVIX")
    nq_p, nq_c = fetch_yahoo("NQ=F")
    nk_p, nk_c = fetch_yahoo("NK=F")
    es_p, es_c = fetch_yahoo("ES=F")
    us10y_p, us10y_c = fetch_yahoo("%5ETNX")

    # 為替 (USD/JPY)
    fx = get_json("https://api.frankfurter.app/latest?from=USD&to=JPY")
    usd_jpy = fx["rates"]["JPY"] if fx and "rates" in fx else 0.0

    return {
        "gold_price": gold_p, "gold_change": gold_c,
        "wti_price": wti_p, "wti_change": wti_c,
        "usd_jpy": usd_jpy,
        "vix_price": vix_p, "vix_change": vix_c,
        "nq_price": nq_p, "nq_change": nq_c,
        "nk_price": nk_p, "nk_change": nk_c,
        "es_price": es_p, "es_change": es_c,
        "us10y_price": us10y_p, "us10y_change": us10y_c,
    }

# ============================
# ロジック判定
# ============================

def detect_mode(vix_price: float) -> str:
    if vix_price == 0.0: return "transition"
    if vix_price >= 25: return "war"   # 警戒水準を25に引き上げ
    if vix_price <= 16: return "peace" # 安定水準を16に設定
    return "transition"

def calc_war_score(d):
    """有事からのリバウンド（リスクオン回帰）を測定"""
    score = 0
    if d["gold_change"] < 0: score += 15
    if d["wti_change"] < 0: score += 15
    if d["vix_change"] <= -5: score += 25
    elif d["vix_change"] < 0: score += 10
    if d["nq_change"] >= 1: score += 15
    if d["nk_change"] >= 1: score += 15
    if d["us10y_change"] < 0: score += 10 # 安全資産からの資金抜け
    return score

def calc_peace_score(d):
    """安定相場でのトレンド強度を測定"""
    score = 0
    if d["us10y_change"] < 0: score += 20 # 金利低下
    if d["nq_change"] > 0.5: score += 20
    if d["es_change"] > 0.5: score += 20
    if d["nk_change"] > 0.5: score += 20
    if d["usd_jpy"] >= 150: score += 20  # 円安寄与
    return score

# ============================
# メッセージ構築
# ============================

def build_status_msg(d):
    lines = [
        f"・VIX  : {d['vix_price']:.2f} ({d['vix_change']:+.2f}%)",
        f"・米10Y: {d['us10y_price']:.2f} ({d['us10y_change']:+.2f}%)",
        f"・ドル円: {d['usd_jpy']:.2f}",
        f"・日経先: {d['nk_price']:.0f} ({d['nk_change']:+.2f}%)",
        f"・NQ先 : {d['nq_price']:.0f} ({d['nq_change']:+.2f}%)",
    ]
    return "\n".join(lines)

def main():
    d = get_market_data()
    mode = detect_mode(d["vix_price"])
    
    msg = []
    if mode == "war":
        score = calc_war_score(d)
        msg.append("🚨 【戦時モード】相場反転判定")
        msg.append(build_status_msg(d))
        msg.append(f"\n反転スコア: {score}点")
        if score >= 70: msg.append("🔥 リスクオン転換の期待大")
        elif score >= 40: msg.append("👀 反転の兆しあり（準備）")
        else: msg.append("⚠️ 有事継続。慎重姿勢を維持")
        
    elif mode == "peace":
        score = calc_peace_score(d)
        msg.append("☀️ 【平時モード】トレンド判定")
        msg.append(build_status_msg(d))
        msg.append(f"\nトレンドスコア: {score}点")
        if score >= 70: msg.append("📈 強い上昇トレンド")
        elif score >= 40: msg.append("🔍 緩やかな買い優勢")
        else: msg.append("☁️ トレンド不明瞭・調整中")
        
    else:
        msg.append("⚖️ 【移行期】様子見推奨")
        msg.append(build_status_msg(d))
        msg.append("\nVIXが中間に位置しています。無理なエントリーは避けましょう。")

    # 欠落データ確認
    missing = [k for k, v in d.items() if v == 0.0]
    if missing:
        msg.append(f"\n(※一部データ取得失敗: {len(missing)}件)")

    send_line("\n".join(msg))

if __name__ == "__main__":
    main()
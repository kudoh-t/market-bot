import requests
import json
import os
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

# ============================
# 設定：環境変数
# ============================
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")


def send_line(text: str):
    if not LINE_ACCESS_TOKEN or not LINE_USER_ID:
        return
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_ACCESS_TOKEN}"
    }
    body = {
        "to": LINE_USER_ID,
        "messages": [{"type": "text", "text": text}]
    }
    try:
        requests.post(url, headers=headers, data=json.dumps(body), timeout=10)
    except Exception:
        pass


# ============================
# 判定・解説ロジック
# ============================
def get_vix_analysis(v_spot, v_fut, is_estimated):
    if v_spot is None:
        return "⚠️VIX現物データ取得失敗：リスク指標の精度低下に注意。"
    if is_estimated or v_fut is None:
        return "⚠️VIX先物データ取得失敗：現物のみで診断中。乖離判定は参考値です。"

    diff = v_spot - v_fut
    if diff > 0.5:
        return f"🚨異常乖離(逆転)：現物が先物を{diff:.2f}上回るパニック状態。歴史的に底打ちが近いサインです。"
    elif diff < -1.0:
        return f"✅正常乖離(順鞘)：先物の方が高い正常な状態。市場のパニックは落ち着いています。"
    else:
        return "😐均衡状態：現物と先物が同水準。方向感を模索中です。"


def get_fgi_detail(now_val, prev_val):
    if now_val is None:
        return "⚠️Fear & Greed Index：データ取得失敗（CNN APIエラー）"

    change = None
    if prev_val is not None:
        change = now_val - prev_val

    if change is None:
        change_str = "前日比：取得失敗"
    else:
        sign = "+" if change > 0 else ""
        change_str = f"前日比：{sign}{change:.0f}pt"

    if now_val <= 25:
        base = f"🧊指数({now_val}): 極度の恐怖。歴史的には仕込み場になりやすい水準。"
    elif now_val <= 45:
        base = f"😨指数({now_val}): 恐怖。下落への警戒が強い状態。静観が吉。"
    elif now_val <= 55:
        base = f"😐指数({now_val}): 中立。強弱感が拮抗。トレンド待ち。"
    elif now_val <= 75:
        base = f"🚀指数({now_val}): 強欲。過熱感あり。利益確定を優先。"
    else:
        base = f"🚨指数({now_val}): 極度の強欲。急落警戒。"

    return f"{base}（{change_str}）"


def get_yield_comment(spread, us10y_change):
    if spread is None:
        return "⚠️金利データ取得失敗：イールドカーブ判定不可。"
    if spread < 0:
        return "⚠️逆イールド：景気後退の強い予兆。"
    elif spread >= 0.5 and (us10y_change is not None and us10y_change > 0):
        return "⚡急激なスティープニング：長期金利急騰。債券売りに注意。"
    elif 0 <= spread < 0.2:
        return "🔄フラット化：反転の兆し。ただし金利上昇なら株には逆風。"
    else:
        return "✅順イールド：金利体系は正常。ただし金利の上昇速度に注意。"


def get_score_comment(scaled):
    if scaled >= 80:
        return "💎【反転確定ゾーン】複数の反転シグナル点灯。攻めに転じる好機。"
    if scaled >= 50:
        return "📈【反転の兆し】買い戻しの動き。打診買い検討圏内。"
    if scaled >= 30:
        return "⚠️【初期兆候】下げ止まりの兆しはあるが、まだ不安定。慎重に。"
    return "🌑【有事継続】無理な逆張りは避け、キャッシュ保護を優先。"


def analyze_market_action(d):
    actions = []

    if (not d["vxf_is_estimated"]
        and d["vix_price"] is not None
        and d["vxf_price"] is not None
        and d["vix_price"] > d["vxf_price"] + 0.5):
        actions.append("⚠️【VIX逆転】現物が先物を上回る異常事態。パニック売りに乗らず反転待ち。")

    if (d["us10y_change"] is not None and d["us10y_change"] > 1.2
        and d["nq_change"] is not None and d["nq_change"] < -0.8):
        actions.append("📉【金利の重力】長期金利急騰で株価に強い逆風。買い増しは危険。")

    if (d["gold_change"] is not None and d["gold_change"] > 2.0
        and d["wti_change"] is not None and d["wti_change"] > 3.0):
        actions.append("🛢️【有事の動き】金と原油の同時急騰は地政学リスク。株には逆風。")

    return "\n\n".join(actions[:2]) if actions else "🧐【特筆事項なし】目立った歪みなし。トレンド待ち。"


# ============================
# ★ 新規追加：BTCコメント
# ============================
def get_btc_comment(btc_change):
    if btc_change is None:
        return "⚠️BTCデータ取得失敗：判定不可。"

    if btc_change > 1.5:
        return "₿リスクオン気味：BTCが強く、投資家のリスク許容度がやや回復。"
    elif btc_change >= 0:
        return "₿小幅上昇：リスクオフ局面でも資金逃避先として底堅い動き。"
    else:
        return "₿リスクオフ：BTCも売られ、全体的にリスク回避姿勢が強い。"


# ============================
# ★ 修正：日米相対強弱コメント
# ============================
def get_equity_relative_comment(nk_change, nq_change, es_change):
    if nk_change is None or (nq_change is None and es_change is None):
        return "⚠️日米株価指数の相対比較：データ不足のため判定不可。"

    us_changes = []
    if nq_change is not None:
        us_changes.append(nq_change)
    if es_change is not None:
        us_changes.append(es_change)

    if not us_changes:
        return "⚠️日米株価指数の相対比較：米株側データ不足。"

    us_avg = sum(us_changes) / len(us_changes)
    diff = nk_change - us_avg

    if diff >= 1.0:
        return (
            f"🇯🇵日本優位：日経平均先物が米株先物を約{diff:.2f}%上回る動き。"
            "ただし日本株が強いというより、米株の下げが大きい影響が大きい点に注意。"
        )
    elif diff >= 0.3:
        return f"🇯🇵やや日本優位：日経平均先物が米株先物を約{diff:.2f}%上回る。相対的に底堅い動き。"
    elif diff <= -1.0:
        return f"🇺🇸米国優位：日経平均先物が米株先物を約{abs(diff):.2f}%下回る。日本株は出遅れ・売られ気味。"
    elif diff <= -0.3:
        return f"🇺🇸やや米国優位：日経平均先物が米株先物を約{abs(diff):.2f}%下回る。日本株は相対的に弱い。"
    else:
        return "⚖️日米拮抗：日経平均先物と米株先物の騰落率差は小さく、明確な優劣は見られません。"
# ============================
# データ取得
# ============================
def fetch_yahoo_price(symbol):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
        m = res["chart"]["result"][0]["meta"]
        price = m["regularMarketPrice"]
        prev = m["chartPreviousClose"]
        change_pct = (price - prev) / prev * 100
        return price, change_pct
    except Exception:
        return None, None


def fetch_vix_spot():
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX"
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
        r = res["chart"]["result"][0]["meta"]
        p, pr = r["regularMarketPrice"], r["chartPreviousClose"]
        dt = (datetime.fromtimestamp(r["regularMarketTime"], timezone.utc) + timedelta(hours=9)).strftime("%Y.%m.%d")
        change_pct = (p - pr) / pr * 100
        return p, change_pct, dt
    except Exception:
        return None, None, "データ取得失敗"


def fetch_vix_futures():
    """
    Investing.com から VIX先物の現在値と前日比％を取得。
    取得失敗時は (None, None, True) を返す。
    """
    try:
        url = "https://www.investing.com/indices/us-spx-vix-futures"
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")

        price_el = soup.select_one('[data-test="instrument-price-last"]')
        change_pct_el = soup.select_one('[data-test="instrument-price-change-percent"]')

        if price_el is None or change_pct_el is None:
            return None, None, True

        price_text = price_el.text.replace(",", "").strip()
        price = float(price_text)

        change_pct_text = change_pct_el.text.strip()
        change_pct_text = change_pct_text.replace("%", "").replace("+", "").strip()
        change_pct = float(change_pct_text)

        return price, change_pct, False
    except Exception:
        return None, None, True


def fetch_fgi():
    """
    Fear & Greed Index の現在値と前日値を取得。
    取得失敗時は (None, None)。
    """
    try:
        res = requests.get(
            "https://production.dataviz.cnn.io/index/feargreed/static/feargreed",
            headers={"User-Agent": "Mozilla/5.0"}, timeout=10
        ).json()
        now_val = int(res["fgi"]["now"]["value"])
        prev_val = None
        if "previous" in res["fgi"] and "value" in res["fgi"]["previous"]:
            prev_val = int(res["fgi"]["previous"]["value"])
        return now_val, prev_val
    except Exception:
        return None, None


def get_market_data():
    d = {}

    # --- VIX現物 ---
    d["vix_price"], d["vix_change"], d["data_date"] = fetch_vix_spot()

    # --- VIX先物 ---
    vxf_price, vxf_change, vxf_is_estimated = fetch_vix_futures()
    d["vxf_price"], d["vxf_change"], d["vxf_is_estimated"] = vxf_price, vxf_change, vxf_is_estimated

    # --- Fear & Greed Index ---
    fgi_now, fgi_prev = fetch_fgi()
    d["fgi_score"], d["fgi_prev"] = fgi_now, fgi_prev

    # --- その他マーケットデータ（Yahoo） ---
    targets = {
        "gold": "GC=F",
        "wti": "CL=F",
        "nq": "NQ=F",
        "nk": "NK=F",
        "es": "ES=F",
        "us10y": "%5ETNX",
        "us2y": "%5EIRX",
        "btc": "BTC-USD",
    }

    for k, s in targets.items():
        price, change = fetch_yahoo_price(s)
        d[f"{k}_price"], d[f"{k}_change"] = price, change

    # --- イールドスプレッド ---
    if d["us10y_price"] is None or d["us2y_price"] is None:
        d["yield_spread"] = None
    else:
        d["yield_spread"] = d["us10y_price"] - d["us2y_price"]

    d["yield_text"] = get_yield_comment(d["yield_spread"], d["us10y_change"])

    return d


# ============================
# 表示用ユーティリティ
# ============================
def fmt_price_change(price, change):
    if price is None:
        return "取得失敗（前日比：取得失敗）"
    if change is None:
        return f"{price:.2f}（前日比：取得失敗）"
    sign = "+" if change > 0 else ""
    return f"{price:.2f}（前日比：{sign}{change:.2f}%）"


def fmt_price_change_int(price, change):
    if price is None:
        return "取得失敗（前日比：取得失敗）"
    if change is None:
        return f"{price:.0f}（前日比：取得失敗）"
    sign = "+" if change > 0 else ""
    return f"{price:.0f}（前日比：{sign}{change:.2f}%）"


def fmt_price_change_one_decimal(price, change):
    if price is None:
        return "取得失敗（前日比：取得失敗）"
    if change is None:
        return f"{price:.1f}（前日比：取得失敗）"
    sign = "+" if change > 0 else ""
    return f"{price:.1f}（前日比：{sign}{change:.2f}%）"


def fmt_yield_spread(spread):
    if spread is None:
        return "取得失敗"
    try:
        return f"{spread:.3f}"
    except Exception:
        return "取得失敗"
# ============================
# メッセージ構築
# ============================
def build_message(d):
    vix_p = d["vix_price"] if d["vix_price"] is not None else 0
    mode, max_s = ("戦時モード：総合反転スコア", 155) if vix_p >= 20 else ("平時モード：トレンドスコア", 135)

    # --- スコア計算 ---
    score = 0
    if vix_p >= 20:
        if (not d["vxf_is_estimated"]
            and d["vix_price"] is not None
            and d["vxf_price"] is not None
            and d["vix_price"] > d["vxf_price"]):
            score += 30
        if d["vix_change"] is not None and d["vix_change"] <= -5:
            score += 25
        if d["us2y_change"] is not None and d["us2y_change"] < 0:
            score += 20
        if d["yield_spread"] is not None and d["yield_spread"] < 0:
            score += 20
        if d["btc_change"] is not None and d["btc_change"] >= 3:
            score += 15
        if d["nq_change"] is not None and d["nq_change"] > 0:
            score += 25
        if d["es_change"] is not None and d["es_change"] > 0:
            score += 20

    scaled = min(max(int(score / max_s * 100), 0), 100)

    # --- VIX先物表示 ---
    if d["vxf_price"] is None:
        vxf_display = "取得失敗（前日比：取得失敗）"
    else:
        if d["vxf_change"] is None:
            vxf_display = f"{d['vxf_price']:.2f}（前日比：取得失敗）"
        else:
            sign = "+" if d["vxf_change"] > 0 else ""
            vxf_display = f"{d['vxf_price']:.2f}（前日比：{sign}{d['vxf_change']:.2f}%）"

    # --- 日米相対強弱コメント ---
    equity_relative_comment = get_equity_relative_comment(
        d["nk_change"], d["nq_change"], d["es_change"]
    )

    msg = [
        f"【{datetime.now().strftime('%Y.%m.%d')} {mode}】",
        f"📅 データ日：{d['data_date']}\n",

        "▼ 投資家心理 (Fear & Greed Index)",
        f"{get_fgi_detail(d['fgi_score'], d['fgi_prev'])}\n",

        "▼ 主要リスク指標",
        f"VIX現物: {fmt_price_change(d['vix_price'], d['vix_change'])}",
        f"VIX先物: {vxf_display}",
        f" 💡 {get_vix_analysis(d['vix_price'], d['vxf_price'], d['vxf_is_estimated'])}\n",

        "▼ 金利・イールドカーブ",
        f"・米2年金利 : {fmt_price_change(d['us2y_price'], d['us2y_change'])}",
        f"・米10年金利: {fmt_price_change(d['us10y_price'], d['us10y_change'])}",
        f"・金利差(10Y-2Y): {fmt_yield_spread(d['yield_spread'])}",
        f"   💡 {d['yield_text']}\n",

        "▼ 商品（コモディティ）",
        f"・ゴールド : {fmt_price_change_one_decimal(d['gold_price'], d['gold_change'])}",
        f"・WTI原油  : {fmt_price_change_one_decimal(d['wti_price'], d['wti_change'])}\n",

        "▼ 暗号資産",
        f"・BTC : ${fmt_price_change_int(d['btc_price'], d['btc_change'])}",
        f"   💡 {get_btc_comment(d['btc_change'])}\n",

        "▼ 株価指数",
        f"・NASDAQ先物   : {fmt_price_change_one_decimal(d['nq_price'], d['nq_change'])}",
        f"・日経平均先物 : {fmt_price_change_one_decimal(d['nk_price'], d['nk_change'])}",
        f"・S&P500先物   : {fmt_price_change_one_decimal(d['es_price'], d['es_change'])}\n",

        "▼ 日米相対強弱",
        equity_relative_comment + "\n",

        f"⚖️ スコア評価：{scaled}点 / 100",
        f"（生スコア: {score} / {max_s}）",
        f"{get_score_comment(scaled)}\n",

        "--------------------------",
        "💡 【行動指針】",
        analyze_market_action(d)
    ]

    return "\n".join(msg)


# ============================
# メイン処理
# ============================
def main():
    data = get_market_data()
    send_line(build_message(data))


if __name__ == "__main__":
    main()

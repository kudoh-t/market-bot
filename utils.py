# ============================
# 共通ユーティリティ関数
# ============================

def safe_float(v, default=None):
    """
    数値に変換できない場合は default を返す
    """
    try:
        return float(v)
    except:
        return default


def safe_percent(v):
    """
    変化率（%）を安全にフォーマット
    """
    try:
        return f"{v:+.2f}%"
    except:
        return "N/A"


def safe_format(value, change=None, decimals=2):
    """
    市場データの共通フォーマット
    例: 123.45（+1.23%）
    """
    if value is None:
        return "取得失敗"

    try:
        value_str = f"{value:.{decimals}f}"
    except:
        value_str = str(value)

    if change is None:
        return value_str

    try:
        change_str = f"{change:+.2f}%"
    except:
        change_str = "N/A"

    return f"{value_str}（{change_str}）"


def truncate_list(items, n=3):
    """
    ニュースなどのリストを上位 n 件に制限
    """
    return items[:n]


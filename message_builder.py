# --- 3. VIX ---
"▼ 3. リスク指標 (VIX)",
f" ・VIX現物: {safe_fmt(d.get('vix'))}",
f" ・VIX先物{'※推定値' if d.get('vix_f_est') else ''}: {safe_fmt(d.get('vix_f'))}\n",

# --- 5. 商品 ---
"▼ 5. 商品",
f" ・原油(WTI): {safe_fmt(d.get('wti'))}",
f" ・金 (Gold): {safe_fmt(d.get('gold'), 1)}",
f" ・銀 (Silver): {safe_fmt(d.get('silver'))}",
f" ・銅 (Copper): {safe_fmt(d.get('copper'))}",
f" ・天然ガス: {safe_fmt(d.get('natgas'))}\n",

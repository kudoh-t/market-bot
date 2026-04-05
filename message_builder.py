# ここから下が修正箇所
    for cat, label in {"geopolitics":"【地政学】","monetary":"【金融政策】","other":"【その他】"}.items():
        items = classified["categories"].get(cat, [])
        if items:
            msg.append(label)
            for it in items[:2]:
                # タイトルに出所(source)と個別点数を連結するように変更
                src = it.get('source', '不明')
                indiv_score = NEWS_SOURCE_SCORE.get(src, 50)
                msg.append(f"・{it['title']} ({src}:{indiv_score})")

    # 合計スコアの表示行を新たに追加
    msg.append(f"\n[ニュース判定スコア] 戦時:{n_war} / 平時:{n_peace}")
    # 修正箇所ここまで
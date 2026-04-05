def send_line(message):
    token = os.getenv("LINE_TOKEN")
    if not token:
        print("LINE_TOKEN が設定されていません")
        return

    url = "https://notify-api.line.me/api/notify"
    headers = {"Authorization": f"Bearer {token}"}
    data = {"message": message}

    # GitHub Actions の DNS 不安定対策：最大3回リトライ
    for i in range(3):
        try:
            response = requests.post(url, headers=headers, data=data, timeout=10)
            if response.status_code == 200:
                print("LINE送信成功")
                return
            else:
                print(f"LINE送信失敗（{i+1}回目）: {response.status_code}")
        except Exception as e:
            print(f"LINE送信エラー（{i+1}回目）: {e}")

        # 失敗したら3秒待って再試行
        time.sleep(3)

    print("LINE送信に失敗しました（リトライ上限）")
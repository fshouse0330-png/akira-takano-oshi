"""
高野洸 公式サイト スケジュール自動取得スクリプト
GitHub Actionsで毎日自動実行されます
"""

import requests
from bs4 import BeautifulSoup
import json
import re
import time
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
BASE_URL = "https://takano-akira.net"
SCHEDULE_URL = f"{BASE_URL}/contents/schedule"

CATEGORIES = ["LIVE","TV","RADIO","STAGE","EVENT","RELEASE","WEB","MAGAZINE","CINEMA","BOOK","NEWS"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
}

def fetch_page(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        r.encoding = "utf-8"
        return r.text
    except Exception as e:
        print(f"[ERROR] fetch {url}: {e}")
        return None

def parse_schedule_page(html, existing_ids):
    events = []
    if not html:
        return events, False

    soup = BeautifulSoup(html, "html.parser")

    # パターン1: リスト項目から日付・カテゴリ・タイトルを取得
    pattern = re.compile(
        r'(\d{4})\s+(\d{2})\.(\d{2})\s+(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+'
        r'(LIVE|TV|RADIO|STAGE|EVENT|RELEASE|WEB|MAGAZINE|CINEMA|BOOK|NEWS)\s*(.+)',
        re.IGNORECASE
    )

    # テキストコンテンツから全体をスキャン
    full_text = soup.get_text(separator="\n")
    for line in full_text.split("\n"):
        line = line.strip()
        m = pattern.match(line)
        if not m:
            continue
        year, mm, dd = m.group(1), m.group(2), m.group(3)
        cat = m.group(5).upper()
        title = m.group(6).strip()
        if not title or len(title) < 3:
            continue

        date_str = f"{year}-{mm}-{dd}"
        ext_id = f"{date_str}_{title[:30]}"
        if ext_id in existing_ids:
            continue

        events.append({
            "id": f"{date_str}_{hash(title) % 99999:05d}",
            "date": date_str,
            "category": cat,
            "title": title,
            "venue": "",
            "url": "",
            "memo": "",
            "source": "fetched",
            "externalId": ext_id
        })
        existing_ids.add(ext_id)

    # パターン2: aタグからURLとタイトルを補完
    for a in soup.find_all("a", href=re.compile(r"/contents/\d+")):
        href = a.get("href", "")
        title = a.get_text(strip=True)
        if not title or len(title) < 4 or len(title) > 200:
            continue

        # 親要素から日付・カテゴリを探す
        parent = a.find_parent("li") or a.find_parent("div")
        if not parent:
            continue
        parent_text = parent.get_text()
        dm = re.search(r'(\d{4})\s+(\d{2})\.(\d{2})', parent_text)
        cm = re.search(r'\b(LIVE|TV|RADIO|STAGE|EVENT|RELEASE|WEB|MAGAZINE|CINEMA|BOOK|NEWS)\b', parent_text, re.I)
        if not dm:
            continue

        year, mm, dd = dm.group(1), dm.group(2), dm.group(3)
        date_str = f"{year}-{mm}-{dd}"
        cat = cm.group(1).upper() if cm else "OTHER"
        full_url = href if href.startswith("http") else BASE_URL + href
        ext_id = f"{date_str}_{title[:30]}"

        if ext_id in existing_ids:
            # URLだけ更新
            for ev in events:
                if ev.get("externalId") == ext_id and not ev.get("url"):
                    ev["url"] = full_url
            continue

        events.append({
            "id": f"{date_str}_{hash(title) % 99999:05d}",
            "date": date_str,
            "category": cat,
            "title": title,
            "venue": "",
            "url": full_url,
            "memo": "",
            "source": "fetched",
            "externalId": ext_id
        })
        existing_ids.add(ext_id)

    # 次ページがあるか確認
    has_next = bool(soup.find("a", string=re.compile(r"次の|›|next", re.I)))
    return events, has_next

def main():
    # 既存データ読み込み
    try:
        with open("data.json", "r", encoding="utf-8") as f:
            existing_data = json.load(f)
    except:
        existing_data = {"events": []}

    existing_events = existing_data.get("events", [])
    existing_ids = set(ev.get("externalId", "") for ev in existing_events)

    all_new_events = []

    # 全カテゴリのスケジュールページを取得（最大3ページ）
    urls_to_fetch = [SCHEDULE_URL]
    for page in range(2, 4):
        urls_to_fetch.append(f"{SCHEDULE_URL}/page/{page}")

    for url in urls_to_fetch:
        print(f"[INFO] Fetching: {url}")
        html = fetch_page(url)
        new_events, _ = parse_schedule_page(html, existing_ids)
        all_new_events.extend(new_events)
        if html:
            time.sleep(1)  # サーバー負荷軽減

    # データをマージ（新しい順）
    merged = existing_events + all_new_events
    merged.sort(key=lambda x: x.get("date", ""), reverse=True)

    output = {
        "events": merged,
        "lastUpdated": datetime.now(JST).strftime("%Y-%m-%d %H:%M JST"),
        "source": SCHEDULE_URL,
        "totalCount": len(merged),
        "newCount": len(all_new_events)
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"[DONE] 新規 {len(all_new_events)}件追加 / 合計 {len(merged)}件")

if __name__ == "__main__":
    main()

"""
高野洸 推し活情報 多ソース自動取得スクリプト
==============================================
取得ソース:
  1. 公式サイト          https://takano-akira.net/contents/schedule
  2. Twitter (RSSHub)    @AKIRAT_official / @akira_t_staff
  3. Twitter (Nitter)    フォールバック
  4. 音楽ナタリー RSS    https://natalie.mu/music
  5. ステージナタリー RSS https://natalie.mu/stage
  6. e+                  https://eplus.jp
  7. ぴあ               https://t.pia.jp
  8. ローチケ            https://l-tike.com
"""

import requests
from bs4 import BeautifulSoup
import json, re, time, xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

JST      = timezone(timedelta(hours=9))
NOW      = datetime.now(JST)
TODAY    = NOW.strftime("%Y-%m-%d")
HEADERS  = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                  "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Accept-Language": "ja,en;q=0.9",
}

# アンバサダー・イベント系キーワード（Twitterから検出）
AMBASSADOR_KW = [
    "アンバサダー", "ambassador", "コラボ", "キャンペーン", "特典",
    "グッズ", "限定", "イベント", "トークショー", "サイン会",
    "握手会", "ファンミ", "ファンミーティング", "プレゼント",
    "抽選", "当選", "スポンサー", "CM", "広告", "モデル",
]
SCHEDULE_KW = [
    "ライブ", "live", "LIVE", "公演", "出演", "舞台", "ミュージカル",
    "ツアー", "tour", "コンサート", "concert", "TV", "テレビ",
    "ラジオ", "radio", "配信", "リリース", "発売", "映画",
]

def uid():
    import random, string
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))

def fetch(url, timeout=12):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        r.encoding = r.apparent_encoding or "utf-8"
        return r.text
    except Exception as e:
        print(f"  [SKIP] {url[:60]} → {e}")
        return None

def to_date(y, m, d):
    try:
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    except:
        return None

def detect_category(text):
    t = text.upper()
    if any(k in t for k in ["LIVE","ライブ","ツアー","TOUR","コンサート"]): return "LIVE"
    if any(k in t for k in ["舞台","ミュージカル","STAGE","公演","刀ミュ","スタミュ","キングダム"]): return "STAGE"
    if any(k in t for k in ["TV","テレビ","放送","出演"]): return "TV"
    if any(k in t for k in ["RADIO","ラジオ"]): return "RADIO"
    if any(k in t for k in ["発売","リリース","シングル","アルバム","RELEASE"]): return "RELEASE"
    if any(k in t for k in ["映画","CINEMA","上映"]): return "CINEMA"
    if any(k in t for k in ["雑誌","MAGAZINE","掲載","表紙"]): return "MAGAZINE"
    if any(k in t for k in ["アンバサダー","コラボ","キャンペーン","CM","AMBASSADOR","EVENT","イベント",
                             "トークショー","サイン","ファンミ","グッズ"]): return "EVENT"
    return "OTHER"

def make_event(date, title, category=None, url="", venue="", source="fetched", source_name=""):
    if not category:
        category = detect_category(title)
    ext_id = f"{date}_{title[:30].strip()}"
    return {
        "id": uid(),
        "date": date,
        "category": category,
        "title": title.strip(),
        "venue": venue,
        "url": url,
        "memo": f"取得元: {source_name}" if source_name else "",
        "source": source,
        "externalId": ext_id,
        "fetchedAt": NOW.strftime("%Y-%m-%d %H:%M JST"),
    }

# ──────────────────────────────────────────
# 1. 公式サイト
# ──────────────────────────────────────────
def scrape_official():
    print("\n[1/8] 公式サイト...")
    results = []
    pat = re.compile(
        r'(\d{4})\s+(\d{2})\.(\d{2})\s+(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+'
        r'(LIVE|TV|RADIO|STAGE|EVENT|RELEASE|WEB|MAGAZINE|CINEMA|BOOK|NEWS)\s*([^\n\r<]{3,})',
        re.IGNORECASE
    )
    for page in range(1, 4):
        url = "https://takano-akira.net/contents/schedule" + (f"/page/{page}" if page > 1 else "")
        html = fetch(url)
        if not html: break
        for m in pat.finditer(html):
            date = to_date(m.group(1), m.group(2), m.group(3))
            if not date: continue
            title = re.sub(r'<[^>]+>', '', m.group(5)).strip()
            cat   = m.group(4).upper()
            if not title or len(title) < 3: continue
            results.append(make_event(date, title, cat, source_name="公式サイト"))
        time.sleep(1)

    # aタグからURL補完
    for page in range(1, 3):
        url = "https://takano-akira.net/contents/schedule" + (f"/page/{page}" if page > 1 else "")
        html = fetch(url)
        if not html: break
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=re.compile(r"/contents/\d+")):
            href  = a.get("href","")
            title = a.get_text(strip=True)
            par   = a.find_parent("li") or a.parent
            if not par or not title: continue
            dm = re.search(r'(\d{4})\s+(\d{2})\.(\d{2})', par.get_text())
            if not dm: continue
            date = to_date(dm.group(1), dm.group(2), dm.group(3))
            if not date: continue
            full_url = href if href.startswith("http") else "https://takano-akira.net" + href
            for ev in results:
                if ev["externalId"].startswith(date) and ev["title"][:20] in title[:25]:
                    if not ev["url"]: ev["url"] = full_url
        time.sleep(1)

    print(f"  → {len(results)}件")
    return results

# ──────────────────────────────────────────
# 2. Twitter via RSSHub（より安定）
# ──────────────────────────────────────────
RSSHUB_INSTANCES = [
    "https://rsshub.app",
    "https://rsshub.rssforever.com",
    "https://hub.slarker.me",
]
TWITTER_ACCOUNTS = ["AKIRAT_official", "akira_t_staff"]

def parse_tweet_date(date_str):
    if not date_str: return TODAY
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(date_str).astimezone(JST).strftime("%Y-%m-%d")
    except: pass
    try:
        return datetime.fromisoformat(date_str.replace("Z","+00:00")).astimezone(JST).strftime("%Y-%m-%d")
    except: pass
    return TODAY

def is_schedule_tweet(text):
    return any(k in text for k in SCHEDULE_KW + AMBASSADOR_KW)

def scrape_twitter_rsshub():
    print("\n[2/8] Twitter (RSSHub)...")
    results = []
    for account in TWITTER_ACCOUNTS:
        fetched = False
        for base in RSSHUB_INSTANCES:
            url = f"{base}/twitter/user/{account}"
            xml_text = fetch(url, timeout=10)
            if not xml_text or "<item>" not in xml_text: continue
            try:
                root  = ET.fromstring(xml_text)
                items = root.findall(".//item")
                for item in items[:30]:
                    title_el = item.find("title")
                    link_el  = item.find("link")
                    date_el  = item.find("pubDate")
                    desc_el  = item.find("description")
                    text = (title_el.text or "") if title_el is not None else ""
                    if desc_el is not None and desc_el.text:
                        text += " " + re.sub(r'<[^>]+>', '', desc_el.text)
                    text = text.strip()
                    if not is_schedule_tweet(text): continue
                    link  = link_el.text if link_el is not None else ""
                    date  = parse_tweet_date(date_el.text if date_el is not None else "")
                    title = f"[Twitter @{account}] {text[:100].replace(chr(10),' ')}"
                    results.append(make_event(date, title, url=link, source_name=f"Twitter @{account}"))
                fetched = True
                print(f"  @{account}: {base} 成功")
                break
            except Exception as e:
                print(f"  @{account}: {base} エラー: {e}")
        if not fetched:
            print(f"  @{account}: RSSHub 全インスタンス失敗")
    print(f"  → {len(results)}件")
    return results

# ──────────────────────────────────────────
# 3. Twitter via Nitter（フォールバック）
# ──────────────────────────────────────────
NITTER_INSTANCES = [
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.net",
    "https://nitter.1d4.us",
]

def scrape_twitter_nitter():
    print("\n[3/8] Twitter (Nitter)...")
    results = []
    for account in TWITTER_ACCOUNTS:
        fetched = False
        for base in NITTER_INSTANCES:
            xml_text = fetch(f"{base}/{account}/rss", timeout=8)
            if not xml_text or "<item>" not in xml_text: continue
            try:
                root  = ET.fromstring(xml_text)
                items = root.findall(".//item")
                for item in items[:25]:
                    title_el = item.find("title")
                    link_el  = item.find("link")
                    date_el  = item.find("pubDate")
                    text = (title_el.text or "").strip()
                    if not is_schedule_tweet(text): continue
                    link  = link_el.text if link_el is not None else ""
                    date  = parse_tweet_date(date_el.text if date_el is not None else "")
                    title = f"[Twitter @{account}] {text[:100].replace(chr(10),' ')}"
                    results.append(make_event(date, title, url=link, source_name=f"Twitter @{account} (Nitter)"))
                fetched = True
                print(f"  @{account}: {base} 成功")
                break
            except: continue
        if not fetched:
            print(f"  @{account}: Nitter 全インスタンス失敗（スキップ）")
    print(f"  → {len(results)}件")
    return results

# ──────────────────────────────────────────
# 4. 音楽ナタリー RSS
# ──────────────────────────────────────────
def scrape_natalie_music():
    print("\n[4/8] 音楽ナタリー...")
    results = []
    xml_text = fetch("https://natalie.mu/music/feed/news")
    if not xml_text: return results
    try:
        root  = ET.fromstring(xml_text)
        for item in root.findall(".//item"):
            title_el = item.find("title")
            link_el  = item.find("link")
            date_el  = item.find("pubDate")
            desc_el  = item.find("description")
            title = (title_el.text or "").strip()
            desc  = re.sub(r'<[^>]+>', '', (desc_el.text or "")) if desc_el is not None else ""
            if "高野洸" not in title + desc: continue
            date = parse_tweet_date(date_el.text if date_el is not None else "")
            link = link_el.text if link_el is not None else ""
            results.append(make_event(date, title, url=link, source_name="音楽ナタリー"))
    except Exception as e:
        print(f"  パースエラー: {e}")
    print(f"  → {len(results)}件")
    return results

# ──────────────────────────────────────────
# 5. ステージナタリー RSS
# ──────────────────────────────────────────
def scrape_natalie_stage():
    print("\n[5/8] ステージナタリー...")
    results = []
    xml_text = fetch("https://natalie.mu/stage/feed/news")
    if not xml_text: return results
    try:
        root  = ET.fromstring(xml_text)
        for item in root.findall(".//item"):
            title_el = item.find("title")
            link_el  = item.find("link")
            date_el  = item.find("pubDate")
            desc_el  = item.find("description")
            title = (title_el.text or "").strip()
            desc  = re.sub(r'<[^>]+>', '', (desc_el.text or "")) if desc_el is not None else ""
            if "高野洸" not in title + desc: continue
            date = parse_tweet_date(date_el.text if date_el is not None else "")
            link = link_el.text if link_el is not None else ""
            results.append(make_event(date, title, "STAGE", url=link, source_name="ステージナタリー"))
    except Exception as e:
        print(f"  パースエラー: {e}")
    print(f"  → {len(results)}件")
    return results

# ──────────────────────────────────────────
# 6. Google ニュース RSS
# ──────────────────────────────────────────
def scrape_google_news():
    print("\n[6/10] Google ニュース...")
    results = []
    # 複数キーワードで検索
    queries = [
        "%E9%AB%98%E9%87%8E%E6%B4%B8",                          # 高野洸
        "%E9%AB%98%E9%87%8E%E6%B4%B8+%E3%82%A2%E3%83%B3%E3%83%90%E3%82%B5%E3%83%80%E3%83%BC",  # 高野洸 アンバサダー
        "%E9%AB%98%E9%87%8E%E6%B4%B8+%E3%82%B3%E3%83%A9%E3%83%9C",  # 高野洸 コラボ
    ]
    seen = set()
    for q in queries:
        url = f"https://news.google.com/rss/search?q={q}&hl=ja&gl=JP&ceid=JP:ja"
        xml_text = fetch(url, timeout=12)
        if not xml_text: continue
        try:
            root  = ET.fromstring(xml_text)
            for item in root.findall(".//item"):
                title_el = item.find("title")
                link_el  = item.find("link")
                date_el  = item.find("pubDate")
                desc_el  = item.find("description")
                title = (title_el.text or "").strip()
                desc  = re.sub(r'<[^>]+>', '', (desc_el.text or "")) if desc_el is not None else ""
                if "高野洸" not in title + desc: continue
                if title in seen: continue
                seen.add(title)
                date = parse_tweet_date(date_el.text if date_el is not None else "")
                link = link_el.text if link_el is not None else ""
                # カテゴリ判定（アンバサダー系を優先検出）
                cat = detect_category(title + " " + desc)
                results.append(make_event(date, title, cat, url=link, source_name="Google ニュース"))
        except Exception as e:
            print(f"  パースエラー: {e}")
        time.sleep(0.5)
    print(f"  → {len(results)}件")
    return results

# ──────────────────────────────────────────
# 7. PR TIMES（プレスリリース）
# ──────────────────────────────────────────
def scrape_prtimes():
    print("\n[7/10] PR TIMES...")
    results = []
    # PR TIMES 検索ページ（高野洸）
    url  = "https://prtimes.jp/main/html/searchrlp/key/%E9%AB%98%E9%87%8E%E6%B4%B8"
    html = fetch(url)
    if not html: return results
    soup = BeautifulSoup(html, "html.parser")
    date_pat = re.compile(r'(\d{4})[年\-/](\d{1,2})[月\-/](\d{1,2})')
    seen = set()
    # PR TIMESの記事リスト
    for item in soup.find_all(["article", "div", "li"],
                               class_=re.compile(r"(press|release|article|list-item|card)", re.I)):
        text  = item.get_text(separator=" ", strip=True)
        if "高野洸" not in text: continue
        dm    = date_pat.search(text)
        date  = to_date(dm.group(1), dm.group(2), dm.group(3)) if dm else TODAY
        a     = item.find("a", href=re.compile(r"/main/html/rd/p/"))
        if not a: a = item.find("a")
        if not a: continue
        title = a.get_text(strip=True)
        if not title or len(title) < 5 or title in seen: continue
        seen.add(title)
        href  = a.get("href","")
        link  = href if href.startswith("http") else "https://prtimes.jp" + href
        cat   = detect_category(title + " " + text[:200])
        results.append(make_event(date, f"[PR] {title}", cat, url=link, source_name="PR TIMES"))
    print(f"  → {len(results)}件")
    return results

# ──────────────────────────────────────────
# 8. e+ 検索
# ──────────────────────────────────────────
def scrape_eplus():
    print("\n[8/10] e+...")
    results = []
    html = fetch("https://eplus.jp/sf/search?keyword=%E9%AB%98%E9%87%8E%E6%B4%B8&genre=1")
    if not html: return results
    soup = BeautifulSoup(html, "html.parser")
    date_pat = re.compile(r'(\d{4})[年/\-](\d{1,2})[月/\-](\d{1,2})')
    seen = set()
    for item in soup.find_all(["li","div","article"], class_=re.compile(r"(event|item|list|card)", re.I)):
        text = item.get_text(separator=" ", strip=True)
        dm   = date_pat.search(text)
        if not dm: continue
        date = to_date(dm.group(1), dm.group(2), dm.group(3))
        if not date or date < TODAY: continue
        a = item.find("a")
        if not a: continue
        title = a.get_text(strip=True)
        if not title or len(title) < 4 or title in seen: continue
        seen.add(title)
        href = a.get("href","")
        link = href if href.startswith("http") else "https://eplus.jp" + href
        results.append(make_event(date, title, url=link, source_name="e+"))
    print(f"  → {len(results)}件")
    return results

# ──────────────────────────────────────────
# 7. ぴあ 検索
# ──────────────────────────────────────────
def scrape_pia():
    print("\n[9/10] ぴあ...")
    results = []
    html = fetch("https://t.pia.jp/pia/search/searchMain.do?kwd=%E9%AB%98%E9%87%8E%E6%B4%B8")
    if not html: return results
    soup = BeautifulSoup(html, "html.parser")
    date_pat = re.compile(r'(\d{4})[年/\-](\d{1,2})[月/\-](\d{1,2})')
    seen = set()
    for item in soup.find_all(["li","div","article"], class_=re.compile(r"(event|item|list|unit)", re.I)):
        text = item.get_text(separator=" ", strip=True)
        dm   = date_pat.search(text)
        if not dm: continue
        date = to_date(dm.group(1), dm.group(2), dm.group(3))
        if not date or date < TODAY: continue
        a = item.find("a")
        if not a: continue
        title = a.get_text(strip=True)
        if not title or len(title) < 4 or title in seen: continue
        seen.add(title)
        href = a.get("href","")
        link = href if href.startswith("http") else "https://t.pia.jp" + href
        results.append(make_event(date, title, url=link, source_name="ぴあ"))
    print(f"  → {len(results)}件")
    return results

# ──────────────────────────────────────────
# 8. ローチケ 検索
# ──────────────────────────────────────────
def scrape_lawson():
    print("\n[10/10] ローチケ...")
    results = []
    html = fetch("https://l-tike.com/search/?keyword=%E9%AB%98%E9%87%8E%E6%B4%B8")
    if not html: return results
    soup = BeautifulSoup(html, "html.parser")
    date_pat = re.compile(r'(\d{4})[年/\-](\d{1,2})[月/\-](\d{1,2})')
    seen = set()
    for item in soup.find_all(["li","div","article"], class_=re.compile(r"(event|item|list|unit|box)", re.I)):
        text = item.get_text(separator=" ", strip=True)
        dm   = date_pat.search(text)
        if not dm: continue
        date = to_date(dm.group(1), dm.group(2), dm.group(3))
        if not date or date < TODAY: continue
        a = item.find("a")
        if not a: continue
        title = a.get_text(strip=True)
        if not title or len(title) < 4 or title in seen: continue
        seen.add(title)
        href = a.get("href","")
        link = href if href.startswith("http") else "https://l-tike.com" + href
        results.append(make_event(date, title, url=link, source_name="ローチケ"))
    print(f"  → {len(results)}件")
    return results

# ──────────────────────────────────────────
# メイン
# ──────────────────────────────────────────
def deduplicate(events):
    seen = {}
    result = []
    for ev in events:
        key = ev["externalId"]
        if key not in seen:
            seen[key] = ev
            result.append(ev)
        else:
            if ev.get("url") and not seen[key].get("url"):
                seen[key]["url"] = ev["url"]
    return result

def main():
    print("=" * 50)
    print(f"高野洸 スケジュール取得 {NOW.strftime('%Y-%m-%d %H:%M JST')}")
    print("=" * 50)

    try:
        with open("data.json", "r", encoding="utf-8") as f:
            existing = json.load(f)
    except:
        existing = {"events": []}

    old_events = existing.get("events", [])
    old_ids    = set(e.get("externalId","") for e in old_events)

    scrapers = [
        ("公式サイト",        scrape_official),
        ("Twitter(RSSHub)",   scrape_twitter_rsshub),
        ("Twitter(Nitter)",   scrape_twitter_nitter),
        ("音楽ナタリー",       scrape_natalie_music),
        ("ステージナタリー",   scrape_natalie_stage),
        ("Google ニュース",    scrape_google_news),
        ("PR TIMES",          scrape_prtimes),
        ("e+",                scrape_eplus),
        ("ぴあ",              scrape_pia),
        ("ローチケ",           scrape_lawson),
    ]

    all_new = []
    source_counts = {}
    for name, fn in scrapers:
        try:
            items = fn()
            fresh = [e for e in items if e["externalId"] not in old_ids]
            all_new.extend(fresh)
            for e in fresh: old_ids.add(e["externalId"])
            source_counts[name] = len(fresh)
        except Exception as e:
            print(f"  [{name}] エラー: {e}")
            source_counts[name] = 0
        time.sleep(0.5)

    merged = deduplicate(old_events + all_new)
    merged.sort(key=lambda x: x.get("date",""), reverse=True)

    print("\n" + "=" * 50)
    print("取得結果:")
    for name, cnt in source_counts.items():
        print(f"  {name}: +{cnt}件")
    print(f"  合計: +{len(all_new)}件 / 総数 {len(merged)}件")
    print("=" * 50)

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump({
            "events":       merged,
            "lastUpdated":  NOW.strftime("%Y-%m-%d %H:%M JST"),
            "source":       "multi-source",
            "totalCount":   len(merged),
            "newCount":     len(all_new),
            "sourceCounts": source_counts,
        }, f, ensure_ascii=False, indent=2)

    print("data.json を更新しました")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Collects articles (RSS) and YouTube videos (channel feeds) into news.json.
Standard library only. Edit the source lists below to taste."""
import json, os, re, sys, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape

# (source name, feed URL, default category: ai | world | india)
ARTICLE_FEEDS = [
    ("TechCrunch", "https://techcrunch.com/category/artificial-intelligence/feed/", "ai"),
    ("The Verge", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml", "ai"),
    ("MIT Technology Review", "https://www.technologyreview.com/topic/artificial-intelligence/feed", "ai"),
    ("BBC News", "https://feeds.bbci.co.uk/news/world/rss.xml", "world"),
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml", "world"),
    ("Deutsche Welle", "https://rss.dw.com/rdf/rss-en-all", "world"),
    ("The Guardian", "https://www.theguardian.com/world/rss", "world"),
    ("Tagesschau", "https://www.tagesschau.de/index~rss2.xml", "world"),
    ("Times of India", "https://timesofindia.indiatimes.com/rssfeedstopstories.cms", "india"),
    ("Times of India", "https://timesofindia.indiatimes.com/rssfeeds/296589292.cms", "world"),
    ("NDTV", "https://feeds.feedburner.com/ndtvnews-india", "india"),
    ("NDTV", "https://feeds.feedburner.com/ndtvnews-world", "world"),
]
# (display name, @handle or channel ID starting with UC, default category)
VIDEO_CHANNELS = [
    ("DW News", "@dwnews", "world"),
    ("Al Jazeera English", "@aljazeeraenglish", "world"),
    ("France 24 English", "@FRANCE24English", "world"),
    ("AI Explained", "@aiexplained-official", "ai"),
    ("Two Minute Papers", "@TwoMinutePapers", "ai"),
    ("WION", "@WIONews", "world"),
    ("NDTV", "@NDTV", "india"),
]
# World items matching these terms are filed under "wars".
WAR_TERMS = ["war", "wars", "warfare", "ukraine", "ukrainian", "kyiv", "russia", "gaza", "hamas",
             "hezbollah", "israel", "idf", "missile", "missiles", "airstrike", "airstrikes",
             "ceasefire", "frontline", "troops", "invasion", "offensive", "shelling", "houthi",
             "houthis", "sudan", "nato", "militants", "battle", "drone strike", "kampf", "krieg"]
WAR_RE = re.compile(r"\b(?:" + "|".join(map(re.escape, WAR_TERMS)) + r")\b", re.I)

MAX_AGE_DAYS, PER_FEED, MAX_ARTICLES, MAX_VIDEOS = 3, 12, 60, 30
UA = {"User-Agent": "Mozilla/5.0 (compatible; PersonalNewsApp/1.0)"}
HERE = os.path.dirname(os.path.abspath(__file__))


def fetch(url, timeout=20):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def local(tag):
    return tag.rsplit("}", 1)[-1]


def parse_date(s):
    if not s:
        return None
    try:
        d = parsedate_to_datetime(s)
    except Exception:
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return None
    return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)


def clean(s, n=220):
    s = re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()
    return s if len(s) <= n else s[:n].rsplit(" ", 1)[0] + "…"


def entries(xml):
    """Yield (fields, element) for every RSS <item> or Atom <entry>."""
    for el in ET.fromstring(xml).iter():
        if local(el.tag) not in ("item", "entry"):
            continue
        f = {}
        for c in el:
            k = local(c.tag)
            if k == "link":
                f.setdefault("link", c.get("href") or (c.text or "").strip())
            elif k in ("title", "pubDate", "published", "updated", "date", "description", "summary", "videoId"):
                f.setdefault(k, (c.text or "").strip())
        yield f, el


def categorize(default, text):
    return "wars" if default == "world" and WAR_RE.search(text) else default


def channel_id(handle, cache):
    if handle.startswith("UC"):
        return handle
    if handle not in cache:
        page = fetch("https://www.youtube.com/" + handle).decode("utf-8", "ignore")
        m = re.search(r'"(?:externalId|channelId)":"(UC[\w-]{22})"', page) or re.search(r"channel/(UC[\w-]{22})", page)
        if not m:
            raise ValueError("channel ID not found for " + handle)
        cache[handle] = m.group(1)
    return cache[handle]


def collect():
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)
    cache_path = os.path.join(HERE, "channel_ids.json")
    cache = json.load(open(cache_path)) if os.path.exists(cache_path) else {}
    items, seen = [], set()

    def add(kind, source, default, f, thumb=None):
        link, title, when = f.get("link"), clean(f.get("title"), 200), parse_date(
            f.get("pubDate") or f.get("published") or f.get("date") or f.get("updated"))
        if not (link and title and when) or when < cutoff or link in seen:
            return False
        seen.add(link)
        summary = "" if kind == "video" else clean(f.get("description") or f.get("summary"))
        items.append({"id": link, "type": kind, "category": categorize(default, title + " " + summary),
                      "title": title, "source": source, "url": link, "thumb": thumb,
                      "summary": summary, "published": when.isoformat()})
        return True

    for source, url, cat in ARTICLE_FEEDS:
        try:
            n = 0
            for f, _ in entries(fetch(url)):
                n += add("article", source, cat, f)
                if n >= PER_FEED:
                    break
            print(f"{source}: {n} articles")
        except Exception as e:
            print(f"{source}: skipped ({e})", file=sys.stderr)

    for name, handle, cat in VIDEO_CHANNELS:
        try:
            cid, n = channel_id(handle, cache), 0
            for f, _ in entries(fetch("https://www.youtube.com/feeds/videos.xml?channel_id=" + cid)):
                vid = f.get("videoId")
                if vid:
                    f["link"] = "https://www.youtube.com/watch?v=" + vid
                    n += add("video", name, cat, f, f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg")
                if n >= PER_FEED:
                    break
            print(f"{name}: {n} videos")
        except Exception as e:
            print(f"{name}: skipped ({e})", file=sys.stderr)

    json.dump(cache, open(cache_path, "w"), indent=1)
    items.sort(key=lambda i: i["published"], reverse=True)
    arts = [i for i in items if i["type"] == "article"][:MAX_ARTICLES]
    vids = [i for i in items if i["type"] == "video"][:MAX_VIDEOS]
    return sorted(arts + vids, key=lambda i: i["published"], reverse=True)


def notify(items):
    """Optional daily briefing via ntfy.sh, sent once a day at NTFY_HOUR (UTC)."""
    topic = os.environ.get("NTFY_TOPIC")
    if not topic or datetime.now(timezone.utc).hour != int(os.environ.get("NTFY_HOUR", "6")):
        return
    lines = []
    for cat, label in (("ai", "AI"), ("wars", "Wars"), ("world", "World"), ("india", "India")):
        lines += [f"{label}: {i['title']}" for i in items if i["category"] == cat and i["type"] == "article"][:2]
    headers = {"Title": "Daily news briefing", "Tags": "newspaper"}
    if os.environ.get("NEWS_APP_URL"):
        headers["Click"] = os.environ["NEWS_APP_URL"]
    try:
        urllib.request.urlopen(urllib.request.Request(
            "https://ntfy.sh/" + topic, data="\n".join(lines).encode(), headers=headers), timeout=20)
    except Exception as e:
        print("notification failed:", e, file=sys.stderr)


if __name__ == "__main__":
    result = collect()
    if not result:
        sys.exit("No items collected; keeping the previous news.json.")
    with open(os.path.join(HERE, "news.json"), "w", encoding="utf-8") as fh:
        json.dump({"updated": datetime.now(timezone.utc).isoformat(), "items": result}, fh, ensure_ascii=False)
    print(f"Wrote {len(result)} items")
    notify(result)

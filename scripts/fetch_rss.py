#!/usr/bin/env python3
import json
import os
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path

DEFAULT_FEEDS = [
    "https://www.smashingmagazine.com/feed/",
    "https://martinfowler.com/feed.atom",
    "https://www.nngroup.com/feed/rss/",
]

OUT_PATH = Path("docs/data/rss/latest.json")


def parse_date(text: str):
    if not text:
        return None
    text = text.strip()
    # RFC822
    try:
        return parsedate_to_datetime(text).timestamp()
    except Exception:
        pass
    # ISO8601 fallback
    iso = text.replace("Z", "+00:00")
    try:
        from datetime import datetime

        return datetime.fromisoformat(iso).timestamp()
    except Exception:
        return None


def get_text(el, names):
    for n in names:
        found = el.find(n)
        if found is not None and found.text:
            return found.text.strip()
    return ""


def parse_feed(xml_text, url):
    root = ET.fromstring(xml_text)

    # RSS
    channel = root.find("channel")
    if channel is not None:
        title = get_text(channel, ["title"]) or url
        items = []
        for it in channel.findall("item")[:10]:
            items.append(
                {
                    "title": get_text(it, ["title"]) or "(no title)",
                    "link": get_text(it, ["link"]),
                    "published": get_text(it, ["pubDate", "dc:date"]),
                }
            )
        return title, items

    # Atom
    ns = {"a": "http://www.w3.org/2005/Atom"}
    title = get_text(root, ["a:title", "title"]) or url
    entries = root.findall("a:entry", ns) or root.findall("entry")
    items = []
    for e in entries[:10]:
        link = ""
        link_el = e.find("a:link", ns) or e.find("link")
        if link_el is not None:
            link = link_el.attrib.get("href", "")
        items.append(
            {
                "title": get_text(e, ["a:title", "title"]) or "(no title)",
                "link": link,
                "published": get_text(e, ["a:updated", "a:published", "updated", "published"]),
            }
        )
    return title, items


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "potato-log-rss-bot/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", errors="replace")


def main():
    raw_urls = os.environ.get("FEED_URLS", "").strip()
    if raw_urls:
        feeds = [u.strip() for u in re.split(r"[,\n]", raw_urls) if u.strip()]
    else:
        feeds = DEFAULT_FEEDS

    out = {
        "generatedAt": int(time.time()),
        "feeds": [],
    }

    failed = 0
    for url in feeds:
        try:
            xml_text = fetch(url)
            feed_title, items = parse_feed(xml_text, url)
            for it in items:
                it["publishedTs"] = parse_date(it.get("published", ""))
            out["feeds"].append(
                {
                    "title": feed_title,
                    "url": url,
                    "items": items,
                }
            )
        except Exception as e:
            failed += 1
            out["feeds"].append(
                {
                    "title": url,
                    "url": url,
                    "error": str(e),
                    "items": [],
                }
            )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # succeed unless all feeds failed
    if failed == len(feeds):
        print("All feeds failed", file=sys.stderr)
        return 1
    print(f"Wrote {OUT_PATH} with {len(feeds)} feeds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

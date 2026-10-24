#!/usr/bin/env python3
"""Collect recent France sovereign-risk headlines from Google News RSS."""
import datetime as dt
import email.utils
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

QUERIES = {
    "Fiscal policy": 'France (budget OR deficit OR debt OR tax OR spending) when:7d',
    "Politics": 'France (government OR parliament OR prime minister OR no confidence) when:7d',
    "Reforms & protests": 'France (reform OR strikes OR protests OR unrest) when:7d',
    "Bond markets": 'France (bond yields OR OAT OR sovereign spread OR credit rating) when:7d',
}
items = []
seen = set()
for topic, query in QUERIES.items():
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": query, "hl": "en-GB", "gl": "GB", "ceid": "GB:en"})
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=25) as resp:
            root = ET.fromstring(resp.read())
        for node in root.findall("./channel/item"):
            title = " ".join(node.findtext("title", "").split())
            link = node.findtext("link", "").strip()
            source = node.findtext("source", "").strip()
            raw_date = node.findtext("pubDate", "").strip()
            try:
                published = email.utils.parsedate_to_datetime(raw_date).astimezone(dt.timezone.utc)
            except (TypeError, ValueError):
                continue
            if not title or not link or not source:
                continue
            # Google News titles often end with the publisher name.
            if title.endswith(" - " + source):
                title = title[:-(len(source) + 3)]
            key = re.sub(r"[^a-z0-9]+", "", title.lower())
            if key in seen:
                continue
            seen.add(key)
            items.append({"title": title, "url": link, "source": source,
                          "published_at_utc": published.isoformat(timespec="seconds"),
                          "topic": topic})
    except Exception as exc:
        print("Feed failed:", topic, exc)
items.sort(key=lambda x: x["published_at_utc"], reverse=True)
if len(items) < 5:
    raise ValueError("Insufficient valid headlines; previous published feed preserved")
output = {"checked_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
          "source": "Google News RSS (publisher-attributed headlines)",
          "items": items[:60]}
path = Path("data/france-news.json")
path.parent.mkdir(exist_ok=True)
path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("Published", len(output["items"]), "news headlines")

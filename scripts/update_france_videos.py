#!/usr/bin/env python3
"""Collect recent France economic and fiscal YouTube reports from channel Atom feeds."""
import datetime as dt
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

CHANNELS = {
    "France 24 English": "UCQfwfsi5VrQ8yKZ-UWmAEFg",
    "Bloomberg Television": "UCIALMKvObZNtJ6AmdCLP7Lg",
    "Reuters": "UChqUTb7kYRX8-EiaN3XFrSQ",
    "DW News": "UCknLrEdhRCp1aegoMqRaCZg",
    "Euronews": "UCW2QcKZiU8aUGg4yxCIditg",
}
NS = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}
FRANCE = re.compile(r"\b(?:france|french|macron|lecornu|paris|oat)\b", re.I)
TOPIC = re.compile(r"\b(?:budget|debt|deficit|fiscal|economy|economic|gdp|growth|recession|inflation|unemployment|jobs|bond|bonds|yield|yields|rating|tax|taxes|parliament|government|prime minister|political crisis|credit|borrowing|spending)\b", re.I)
EXCLUDE = re.compile(r"\b(?:football|tennis|rugby|police shooting|celebrity|fashion|travel guide)\b", re.I)
now = dt.datetime.now(dt.timezone.utc)
cutoff = now - dt.timedelta(days=7)
items = []
for channel, channel_id in CHANNELS.items():
    url = "https://www.youtube.com/feeds/videos.xml?channel_id=" + channel_id
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as response:
            root = ET.fromstring(response.read())
        count = 0
        for entry in root.findall("a:entry", NS):
            title = entry.findtext("a:title", default="", namespaces=NS).strip()
            video_id = entry.findtext("yt:videoId", default="", namespaces=NS)
            published = entry.findtext("a:published", default="", namespaces=NS)
            if not video_id or not published:
                continue
            when = dt.datetime.fromisoformat(published.replace("Z", "+00:00"))
            if not (cutoff <= when <= now) or not FRANCE.search(title) or EXCLUDE.search(title):
                continue
            items.append({"title": title, "channel": channel, "url": "https://www.youtube.com/watch?v=" + video_id, "published_at_utc": when.isoformat(timespec="seconds")})
            count += 1
        print(channel, "matching videos:", count)
    except Exception as exc:
        print("Feed failed:", channel, exc)
items.sort(key=lambda x: (bool(TOPIC.search(x["title"])), x["published_at_utc"]), reverse=True)
path = Path("data/france-videos.json")
if not items:
    print("WARNING: No matching videos; retaining previous feed if present")
    if not path.exists():
        path.write_text(json.dumps({"checked_at_utc": now.isoformat(), "items": []}, indent=2) + "\n")
else:
    path.write_text(json.dumps({"checked_at_utc": now.isoformat(timespec="seconds"), "items": items[:12]}, ensure_ascii=False, indent=2) + "\n")
print("Collected", len(items), "videos")

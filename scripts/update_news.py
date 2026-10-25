#!/usr/bin/env python3
"""Collect publicly indexed France sovereign-risk headlines without scraping paywalls."""
import datetime as dt
import email.utils
import json
import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)
NOW = dt.datetime.now(dt.timezone.utc)
SEARCHES = {
    "Fiscal policy": 'France (budget OR deficit OR debt OR fiscal) when:7d',
    "Politics": 'France (government OR parliament OR Lecornu OR confidence vote) when:7d',
    "Reforms & protests": 'France (protests OR strikes OR pension reform) when:7d',
    "Bond markets": 'France (OAT OR sovereign bonds OR bond yields OR Moody\'s OR Fitch OR S&P) when:7d',
}
TRUSTED = ("reuters", "financial times", "bloomberg", "the economist", "le monde",
           "les echos", "associated press", "politico", "france 24", "euronews",
           "rfi", "insee", "banque de france", "agence france", "barron's")
def get(url):
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 FranceMonitor/1.0"})
    with urllib.request.urlopen(request, timeout=25) as response:
        return response.read()
def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", s.casefold()).strip()
def read_previous(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}
items = []
errors = []
for topic, query in SEARCHES.items():
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({
        "q": query, "hl": "en-GB", "gl": "GB", "ceid": "GB:en"})
    try:
        tree = ET.fromstring(get(url))
        for node in tree.findall("./channel/item"):
            title = (node.findtext("title") or "").strip()
            link = (node.findtext("link") or "").strip()
            source_node = node.find("source")
            source = (source_node.text or "").strip() if source_node is not None else ""
            if not title or not link:
                continue
            if not source and " - " in title:
                source = title.rsplit(" - ", 1)[-1]
            if source and norm(source) in norm(title):
                title = title.rsplit(" - ", 1)[0].strip()
            try:
                published = email.utils.parsedate_to_datetime(node.findtext("pubDate")).astimezone(dt.timezone.utc)
            except (TypeError, ValueError):
                continue
            if published > NOW + dt.timedelta(hours=2) or published < NOW - dt.timedelta(days=7):
                continue
            items.append({"title": title, "url": link, "source": source,
                          "topic": topic, "published_at_utc": published.isoformat().replace("+00:00", "Z")})
    except Exception as exc:
        errors.append(f"{topic}: {type(exc).__name__}: {exc}")
unique = {}
for item in sorted(items, key=lambda x: x["published_at_utc"], reverse=True):
    key = norm(item["title"])
    if key and key not in unique:
        unique[key] = item
fresh = list(unique.values())[:100]
news_path = DATA / "france-news.json"
previous = read_previous(news_path)
if fresh:
    news_path.write_text(json.dumps({"checked_at_utc": NOW.isoformat().replace("+00:00", "Z"),
        "items": fresh, "source_method": "Google News RSS headlines; not independently verified",
        "collection_errors": errors}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
else:
    if not previous.get("items"):
        raise SystemExit("No news collected and no previous valid news file; refusing empty publication. " + str(errors))
    print("No new articles; retaining last successful news file", errors)
ratings = [x for x in fresh if re.search(r"moody|fitch|s&p|standard.{0,4}poor|credit rating|downgrad", x["title"], re.I)]
ratings_path = DATA / "ratings-watch.json"
if ratings:
    ratings_path.write_text(json.dumps({"checked_at_utc": NOW.isoformat().replace("+00:00", "Z"),
        "items": ratings[:20], "note": "Unverified headlines, not official rating actions"},
        ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"Collected {len(fresh)} unique headlines; {len(ratings)} ratings leads; errors={errors}")

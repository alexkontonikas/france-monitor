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
    "Fiscal policy": 'France budget deficit debt public finances when:7d',
    "Macroeconomy": 'France GDP growth unemployment jobs inflation economy when:7d',
    "Bond markets": 'France bond yields OAT spread sovereign credit rating when:7d',
    "Fiscal politics": 'France government parliament budget vote fiscal reform when:7d',
}
# Exact publisher names only: never accept a source merely because it contains a trusted name.
TRUSTED_PUBLISHERS = {
    "reuters","bloomberg","bloomberg news","financial times","ft.com",
    "associated press","ap news","ap","agence france-presse","afp","afp fact check",
    "les echos","les échos","le monde","le monde english","france 24",
    "the guardian","the new york times","the wall street journal",
    "the economist","bbc","bbc news","cnbc","euronews","politico",
    "politico europe","the washington post","the times","sky news",
    "rfi","radio france internationale","franceinfo","france info",
    "la tribune","le figaro","libération","liberation","deutsche welle",
    "bfmtv","l'opinion","l'express","le parisien","public sénat",
    "france inter","france culture","ouest-france","sud ouest",
    "challenges","capital","le point","l'obs","20 minutes",
    "dw","the independent","marketwatch","barron's","barrons",
    "cnn","cnn international","nbc news","nbcnews.com","msnbc","euronews","investing.com","yahoo finance","the telegraph","the economic times",
    "business insider","fortune","the conversation","france 24 english"
}
def approved(source):
    return " ".join(source.casefold().split()) in TRUSTED_PUBLISHERS

FRENCH_QUERIES = {
    "Fiscal policy": "France budget déficit dette finances publiques when:7d",
    "Macroeconomy": "France croissance PIB chômage emploi inflation when:7d",
    "Bond markets": "France OAT rendement obligations notation souveraine when:7d",
    "Fiscal politics": "France gouvernement vote budget motion censure when:7d",
}
ENGLISH_EXTRA_QUERIES = {
    "Fiscal policy": ["French fiscal deficit budget 2027 when:7d", "France public debt spending taxes when:7d"],
    "Macroeconomy": ["France GDP economic growth INSEE when:7d", "France unemployment employment inflation when:7d"],
    "Bond markets": ["French OAT German bund yield spread when:7d", "France Fitch Moody S&P sovereign rating when:7d"],
    "Fiscal politics": ["France parliament budget confidence vote when:7d"],
}
FEEDS = [(topic, query, "en-GB", "GB", "GB:en") for topic, query in QUERIES.items()]
FEEDS += [(topic, query, "en-GB", "GB", "GB:en") for topic, queries in ENGLISH_EXTRA_QUERIES.items() for query in queries]
FEEDS += [(topic, query, "fr-FR", "FR", "FR:fr") for topic, query in FRENCH_QUERIES.items()]
# Reject unrelated international, sport and entertainment stories before publication.
FRANCE_TERMS = re.compile(r"\b(?:france|french|français|française|macron|lecornu|oat|paris)\b", re.I)
ECONOMIC_TERMS = re.compile(r"\b(?:budget|fiscal|deficit|déficit|debt|dette|tax|taxes|impôt|impôts|spending|dépenses|economy|economic|économie|économique|growth|croissance|inflation|recession|récession|employment|unemployment|emploi|chômage|chomage|jobs|gdp|pib|bond|bonds|obligation|obligations|yield|yields|rendement|spread|oat|rating|notation|sovereign|souverain|borrowing|emprunt|finances publiques|confidence vote|motion de censure)\b", re.I)
OFF_TOPIC = re.compile(r"\b(?:nfl|football américain|grand prix|formula 1|tennis|champions league|rugby|celebrity|police|policier|arrest|interpellation|petrol bomb|manifestation|protest|grève|strike|riot|émeute|student|étudiant)\b", re.I)
FOREIGN_FOCUS = re.compile(r"\b(?:sénégal|senegal|albania|albanie|ukraine|russia|russie)\b", re.I)
def headline_relevant(title):
    return bool(FRANCE_TERMS.search(title) and ECONOMIC_TERMS.search(title)
                and not FOREIGN_FOCUS.search(title) and not OFF_TOPIC.search(title))
def classify(title):
    if re.search(r"\b(?:oat|bond|bonds|obligation|obligations|yield|yields|spread|rating|notation|sovereign|souverain)\b", title, re.I):
        return "Bond markets"
    if re.search(r"\b(?:budget|deficit|déficit|debt|dette|fiscal|tax|impôt|spending|dépenses|finances publiques)\b", title, re.I):
        return "Fiscal policy"
    if re.search(r"\b(?:gdp|pib|growth|croissance|employment|unemployment|emploi|chômage|chomage|inflation|economy|économie)\b", title, re.I):
        return "Macroeconomy"
    return "Fiscal politics"

items = []
seen = set()
for topic, query, language, country, edition in FEEDS:
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": query, "hl": language, "gl": country, "ceid": edition})
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
            if not title or not link or not source or not approved(source):
                continue
            # Google News titles often end with the publisher name.
            if title.endswith(" - " + source):
                title = title[:-(len(source) + 3)]
            if not headline_relevant(title):
                continue
            key = re.sub(r"[^a-z0-9]+", "", title.lower())
            if key in seen:
                continue
            seen.add(key)
            items.append({"title": title, "url": link, "source": source,
                          "published_at_utc": published.isoformat(timespec="seconds"),
                          "topic": classify(title)})
    except Exception as exc:
        print("Feed failed:", topic, language, exc)
# Publish articles from the last seven days (UTC), on every refresh.
today = dt.datetime.now(dt.timezone.utc).date()
earliest = today - dt.timedelta(days=6)
items = [x for x in items
         if earliest <= dt.datetime.fromisoformat(x["published_at_utc"]).date() <= today]
# Preserve previously collected qualifying articles within the rolling week.
previous_path = Path("data/france-news.json")
if previous_path.exists():
    try:
        previous = json.loads(previous_path.read_text(encoding="utf-8"))
        known = {re.sub(r"[^a-z0-9]+", "", x["title"].lower()) for x in items}
        for old in previous.get("items", []):
            key = re.sub(r"[^a-z0-9]+", "", old.get("title", "").lower())
            if (key not in known and headline_relevant(old.get("title", ""))
                    and earliest <= dt.datetime.fromisoformat(old["published_at_utc"]).date() <= today):
                old["topic"] = classify(old["title"])
                items.append(old)
                known.add(key)
    except (ValueError, KeyError, TypeError) as exc:
        print("Archive read failed:", exc)
items.sort(key=lambda x: x["published_at_utc"], reverse=True)
# Reserve space for each category before filling remaining slots by recency.
selected = []
selected_keys = set()
for category in QUERIES:
    for article in (x for x in items if x["topic"] == category):
        if len([x for x in selected if x["topic"] == category]) >= 5:
            break
        if article["url"] not in selected_keys:
            selected.append(article)
            selected_keys.add(article["url"])
for article in items:
    if len(selected) >= 100:
        break
    if article["url"] not in selected_keys:
        selected.append(article)
        selected_keys.add(article["url"])
selected.sort(key=lambda x: x["published_at_utc"], reverse=True)
today = dt.datetime.now(dt.timezone.utc).date()
same_day_count = sum(dt.datetime.fromisoformat(x["published_at_utc"]).date() == today for x in selected)
if same_day_count < 5:
    print(f"WARNING: Only {same_day_count} same-day articles")
french_publishers = {"les echos", "les échos", "le monde", "le figaro", "libération",
                     "liberation", "franceinfo", "france info", "rfi", "la tribune",
                     "bfmtv", "l'opinion", "l'express", "le parisien", "public sénat",
                     "france inter", "france culture", "ouest-france", "sud ouest",
                     "challenges", "capital", "le point", "l'obs", "20 minutes"}
if not any(x["source"].casefold() in french_publishers for x in selected):
    print("WARNING: No French-language publishers")
for category in QUERIES:
    if not any(x["topic"] == category for x in selected):
        print(f"WARNING: Missing category: {category}")
if not items:
    print("WARNING: No matching headlines found; retaining previous published feed")
    raise SystemExit(0)
output = {"checked_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
          "source": "Google News RSS (English and French editions; approved publishers only)",
          "items": selected[:25]}
path = Path("data/france-news.json")
path.parent.mkdir(exist_ok=True)
path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("Published", len(output["items"]), "news headlines")

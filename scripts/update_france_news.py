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
    "Fiscal policy": "(budget France OR déficit public France OR dette publique France OR finances publiques France) when:7d",
    "Politics": "(gouvernement français OR Assemblée nationale OR premier ministre France OR motion de censure France) when:7d",
    "Reforms & protests": "(manifestations France OR grève France OR réforme France OR mobilisation France) when:7d",
    "Bond markets": "(OAT France OR obligations françaises OR taux souverains France OR notation France) when:7d"
}

ENGLISH_EXTRA_QUERIES = {
    "Fiscal policy": [
        "France fiscal deficit budget negotiations public debt when:3d",
        "French government borrowing spending cuts tax budget crisis when:3d"],
    "Politics": [
        "France political crisis minority government confidence vote parliament when:3d",
        "French prime minister coalition government budget vote when:3d"],
    "Reforms & protests": [
        "France demonstrations strikes unions pension reform unrest when:3d",
        "French protests riots policing economic impact when:3d"],
    "Bond markets": [
        "French OAT yields German bund spread bond selloff when:3d",
        "France sovereign credit rating Moody's Fitch S&P investors when:3d"]
}
GENERAL_ENGLISH_QUERIES = {
    "Politics": ["France news when:2d", "France political crisis when:3d", "Macron France latest news when:2d"],
    "Reforms & protests": ["France protests when:2d", "France riots arrests demonstrations when:2d"],
    "Fiscal policy": ["France economy budget debt news when:3d"],
    "Bond markets": ["France bonds markets yields news when:3d"],
}
FEEDS = [(topic, query, "en-GB", "GB", "GB:en") for topic, query in QUERIES.items()]
FEEDS += [(topic, query, "en-GB", "GB", "GB:en") for topic, queries in GENERAL_ENGLISH_QUERIES.items() for query in queries]
FEEDS += [(topic, query, "en-GB", "GB", "GB:en") for topic, queries in ENGLISH_EXTRA_QUERIES.items() for query in queries]
FEEDS += [(topic, query, "fr-FR", "FR", "FR:fr") for topic, query in FRENCH_QUERIES.items()]
# Reject unrelated international, sport and entertainment stories before publication.
FRANCE_TERMS = re.compile(r"\\b(?:france|french|français|française|françaises|paris|macron|le pen|bardella|bayrou|lecornu|assemblée nationale|elysée|élysée|lyon|marseille|oat|bunds?)\\b", re.I)
POLICY_TERMS = re.compile(r"\\b(?:budget|fiscal|deficit|déficit|debt|dette|tax|taxes|impôts|spending|dépenses|economy|economic|économie|économique|growth|croissance|inflation|recession|récession|government|gouvernement|parliament|parlement|assemblée|minister|ministre|macron|le pen|bardella|confidence|censure|election|élection|coalition|reform|réforme|pension|retraite|strike|grève|protest|manifestation|riot|émeute|union|syndicat|unrest|bond|obligation|yield|rendement|spread|oat|rating|notation|sovereign|souverain|investor|investisseur|police|policier|curfew|couvre-feu|arrest|interpellation)\\b",re.I)
OFF_TOPIC = re.compile(r"\\b(?:nfl|football américain|grand prix|formula 1|formule 1|f1|verstappen|motogp|tennis|champions league|ligue 1|nba|olympic|olympique|rugby|celebrity|célébrité|box office)\\b",re.I)
FOREIGN_FOCUS = re.compile(r"^(?:sénégal|senegal|albania|albanie|spain|espagne|ukraine|russia|russie|italy|italie)\\b",re.I)
def headline_relevant(title):
    return bool(FRANCE_TERMS.search(title) and POLICY_TERMS.search(title)
                and not OFF_TOPIC.search(title) and not FOREIGN_FOCUS.search(title))

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
                          "topic": topic})
    except Exception as exc:
        print("Feed failed:", topic, language, exc)
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
if len(items) < 5:
    raise ValueError("Insufficient valid headlines; previous published feed preserved")
output = {"checked_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
          "source": "Google News RSS (English and French editions; approved publishers only)",
          "items": selected[:100]}
path = Path("data/france-news.json")
path.parent.mkdir(exist_ok=True)
path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("Published", len(output["items"]), "news headlines")

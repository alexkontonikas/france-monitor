#!/usr/bin/env python3
"""Transparent headline-based France sovereign-risk tone index (v5)."""
import datetime as dt
import json
import re
import unicodedata
from pathlib import Path

FEED = Path("data/france-news.json")
TARGET = Path("data/france-risk-tone.json")
TODAY = dt.datetime.now(dt.timezone.utc).date().isoformat()

def norm(value):
    value = unicodedata.normalize("NFKD", value.casefold())
    return "".join(c for c in value if not unicodedata.combining(c))

def match(text, phrases):
    return any(re.search(r"(?<!\w)" + re.escape(p) + r"(?!\w)", text) for p in phrases)

# Explicit French focus; a French publisher or the word 'France' in a URL
# does not establish that an article is about France.
FRANCE = ["france", "french", "francais", "francaise", "macron", "lecornu",
          "assemblee nationale", "elysee", "paris", "lyon", "marseille", "oat"]
FOREIGN = ["senegal", "albania", "serbia", "ukraine", "russia", "italy",
           "espagne", "spain", "australia", "australie"]
RISK = [
    (["downgrade", "rating cut", "degradation", "abaissement de note", "default", "defaut"], 2.0),
    (["deficit widens", "deficit rises", "dette augmente", "debt surges",
      "borrowing costs rise", "yield spike", "bond selloff", "taux grimpent"], 1.7),
    (["no confidence", "motion de censure", "government collapses", "government falls",
      "gouvernement renverse", "political crisis", "crise politique"], 1.6),
    (["riots", "emeutes", "violent protests", "violences", "clashes", "affrontements"], 1.2),
    (["strike", "greve", "protests", "manifestations", "blockade", "blocage"], 0.7),
    (["budget deadlock", "budget rejected", "budget rejete", "impasse budgetaire"], 1.5),
    (["recession", "contraction", "shrinks", "chute du pib"], 1.3),
]
POSITIVE = [
    (["upgrade", "rehaussement de note", "rating raised"], 2.0),
    (["deficit narrows", "deficit falls", "deficit recule", "debt declines",
      "dette diminue", "lower borrowing costs", "yields fall"], 1.5),
    (["budget passed", "budget adopted", "budget adopte", "government survives",
      "confidence vote won"], 1.3),
    (["growth accelerates", "croissance accelere", "economic recovery",
      "reprise economique"], 1.0),
    (["protests end", "strike ends", "fin de la greve", "accord trouve"], 0.8),
]
TOPIC_TERMS = ["budget", "deficit", "dette", "debt", "fiscal", "econom",
               "croissance", "growth", "inflation", "tax", "impot", "spending",
               "gouvernement", "government", "parliament", "assemblee",
               "minister", "ministre", "election", "censure", "protest",
               "manifestation", "greve", "strike", "riot", "emeute",
               "bond", "yield", "oat", "rating", "notation", "sovereign",
               "reform", "reforme", "confidence", "blocage", "blockade",
               "recession", "contraction", "shrinks", "macron", "lecornu"]

def evaluate(item):
    title = item.get("title", "")
    t = norm(title)
    if not match(t, FRANCE) or not match(t, TOPIC_TERMS):
        return None
    # Foreign-country focus must not enter a France-only index.
    if match(t, FOREIGN):
        return None
    neg = sum(weight for terms, weight in RISK if match(t, terms))
    pos = sum(weight for terms, weight in POSITIVE if match(t, terms))
    # No directional claim in the headline: neutral, not assumed negative.
    score = round(max(0, min(100, 50 + 20 * (neg - pos))), 1)
    return {"title": title, "url": item.get("url", ""), "source": item.get("source", ""),
            "topic": item.get("topic", ""), "score": score,
            "relevance": round(max(neg, pos), 2),
            "published_at_utc": item.get("published_at_utc", "")}

feed = json.loads(FEED.read_text(encoding="utf-8"))
items = []
seen = set()
for item in feed.get("items", []):
    if item.get("published_at_utc", "")[:10] != TODAY:
        continue
    result = evaluate(item)
    if result is None:
        continue
    key = re.sub(r"[^a-z0-9]+", "", norm(result["title"]))
    if key in seen:
        continue
    seen.add(key)
    items.append(result)

archive = json.loads(TARGET.read_text(encoding="utf-8")) if TARGET.exists() else {}
# Do not plot v4 article-body values as if comparable with v5 headline values.
observations = [o for o in archive.get("observations", [])
                if o.get("method_version") == 5 and o.get("date") != TODAY]
if items:
    score = round(sum(x["score"] for x in items) / len(items), 1)
    # Prioritise directional, relevant articles; include accessible original RSS links.
    featured = sorted(items, key=lambda x: (x["relevance"], abs(x["score"] - 50),
                                              x["published_at_utc"]), reverse=True)[:8]
    observations.append({
        "date": TODAY, "index": score, "article_count": len(items),
        "headline_count": len(feed.get("items", [])),
        "coverage_pct": round(100 * len(items) / max(1, sum(
            x.get("published_at_utc", "")[:10] == TODAY for x in feed.get("items", []))), 1),
        "adverse_count": sum(x["score"] > 50 for x in items),
        "favourable_count": sum(x["score"] < 50 for x in items),
        "neutral_count": sum(x["score"] == 50 for x in items),
        "method_version": 5, "articles": featured
    })
observations.sort(key=lambda x: x["date"])
archive = {
    "method": "Headline-based sovereign-risk tone v5. Transparent bilingual directional phrase rules; 50 neutral, higher more adverse. Descriptive media tone, not a probability of default. Not comparable with former article-body index.",
    "checked_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    "observations": observations[-120:],
    "coverage": {"date": TODAY, "approved_headlines": len(feed.get("items", [])),
                 "headlines_analysed": len(items), "minimum_headlines": 1}
}
TARGET.write_text(json.dumps(archive, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("Headline risk-tone:", len(items), "relevant headlines", "for", TODAY)

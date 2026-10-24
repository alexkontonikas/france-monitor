#!/usr/bin/env python3
"""Daily article-text risk sentiment, only when publisher article bodies are accessible.

Uses trafilatura for extraction and VADER on sovereign-risk-relevant sentences.
No headlines-only fallback. Reports coverage and source metadata, not copyrighted text.
"""
import datetime as dt
import json
import re
from pathlib import Path
from urllib.parse import urlparse
import trafilatura
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

FEED=Path("data/france-news.json")
TARGET=Path("data/france-risk-tone.json")
NEWS=json.loads(FEED.read_text(encoding="utf-8"))
DAY=dt.datetime.now(dt.timezone.utc).date().isoformat()
analyser=SentimentIntensityAnalyzer()
relevant=re.compile(r"\b(france|french|paris|macron|government|parliament|budget|fiscal|debt|deficit|bond|yield|spread|rating|moody|fitch|s&p|credit|oat|tax|spending|reform|unrest|protest|riot)\b",re.I)
# Context that explicitly says a feared rating action did NOT occur is not negative.
affirm=re.compile(r"(?:moody.s|fitch|s&p|rating).{0,95}(?:holds?|keeps?|maintains?|affirms?|unchanged|steady)|(?:avoids?|dodges?|spared|spares|no)\s+(?:a\s+)?downgrade",re.I)
def sentences(text):
    return re.split(r"(?<=[.!?])\s+(?=[A-Z])",re.sub(r"\s+"," ",text))
def assess(text):
    chosen=[s for s in sentences(text) if len(s)>35 and relevant.search(s)]
    if len(chosen)<4:return None
    scores=[]
    for s in chosen:
        v=analyser.polarity_scores(s)["compound"]
        if affirm.search(s):
            # No downgrade is a non-event, not a realised deterioration.
            v=0
        scores.append(v)
    # Higher index = more negative article tone, 50 = neutral.
    return round(50-50*sum(scores)/len(scores),1),len(chosen)
def get_text(url):
    try:
        # Google's RSS links can be blocked or fail to resolve; do not fabricate text.
        html=trafilatura.fetch_url(url)
        if not html:return None,None
        text=trafilatura.extract(html,include_comments=False,include_tables=False,
                                 favor_precision=True)
        if not text or len(text)<800:return None,None
        return text,url
    except Exception as exc:
        print("Extraction failed:",type(exc).__name__)
        return None,None

articles=[]
today=[x for x in NEWS.get("items",[]) if x.get("published_at_utc","")[:10]==DAY]
for item in today[:45]:
    body,link=get_text(item.get("url",""))
    if not body:continue
    result=assess(body)
    if result is None:continue
    score,n=result
    articles.append({"source":item["source"],"url":link,"title":item["title"],
                     "score":score,"relevant_sentences":n})
# Cluster near-duplicate stories by normalized first 12 words of headline.
unique={}
for a in articles:
    key=" ".join(re.findall(r"[a-z0-9]+",a["title"].lower())[:12])
    unique.setdefault(key,a)
articles=list(unique.values())
archive=json.loads(TARGET.read_text(encoding="utf-8")) if TARGET.exists() else {"observations":[]}
archive["method"]="Article-body sentiment v3: trafilatura-extracted accessible articles; VADER on sovereign-risk-relevant sentences. Higher = more negative tone. Not a risk-change or default-probability measure."
archive["checked_at_utc"]=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
archive["observations"]=[o for o in archive.get("observations",[]) if o["date"]!=DAY]
if len(articles)>=5:
    index=round(sum(a["score"] for a in articles)/len(articles),1)
    row={"date":DAY,"index":index,"article_count":len(articles),
         "headline_count":len(today),"coverage_pct":round(100*len(articles)/max(1,len(today)),1),
         "adverse_count":sum(a["score"]>55 for a in articles),
         "favourable_count":sum(a["score"]<45 for a in articles),
         "neutral_count":sum(45<=a["score"]<=55 for a in articles),
         "method_version":3,"articles":articles}
    archive["observations"].append(row)
    archive["observations"].sort(key=lambda x:x["date"])
    print("Full-text index",index,"from",len(articles),"of",len(today),"headlines")
else:
    print("Full-text coverage insufficient:",len(articles),"of",len(today),
          "— no score published")
archive["coverage"]={"date":DAY,"headlines":len(today),"articles_analysed":len(articles),
                     "minimum_articles":5}
TARGET.write_text(json.dumps(archive,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

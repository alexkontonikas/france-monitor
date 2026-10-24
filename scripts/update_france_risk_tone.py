#!/usr/bin/env python3
"""Daily article-text financial sentiment, only when publisher article bodies are accessible.

Uses trafilatura for extraction and ProsusAI/finbert on relevant sentences.
No headlines-only fallback. Reports coverage and source metadata, not copyrighted text.
"""
import datetime as dt
import json
import re
from pathlib import Path
from urllib.parse import urlparse
import trafilatura
from transformers import pipeline

# Independent defence against unapproved sources in older or manually edited feeds.
APPROVED={"reuters","bloomberg","bloomberg news","financial times","ft.com",
"associated press","ap news","ap","agence france-presse","afp","afp fact check",
"les echos","les échos","le monde","le monde english","france 24",
"the guardian","the new york times","the wall street journal","the economist",
"bbc","bbc news","cnbc","euronews","politico","politico europe",
"the washington post","the times","sky news","rfi","radio france internationale",
"franceinfo","france info","la tribune","le figaro","libération","liberation",
"deutsche welle","dw","the independent","marketwatch","barron's","barrons"}
FEED=Path("data/france-news.json")
TARGET=Path("data/france-risk-tone.json")
NEWS=json.loads(FEED.read_text(encoding="utf-8"))
DAY=dt.datetime.now(dt.timezone.utc).date().isoformat()
analyser=pipeline("text-classification",model="ProsusAI/finbert",tokenizer="ProsusAI/finbert",device=-1)
relevant=re.compile(r"\b(france|french|paris|macron|government|parliament|budget|fiscal|debt|deficit|bond|yield|spread|rating|moody|fitch|s&p|credit|oat|tax|spending|reform|unrest|protest|riot)\b",re.I)
# Context that explicitly says a feared rating action did NOT occur is not negative.
affirm=re.compile(r"(?:moody.s|fitch|s&p|rating).{0,95}(?:holds?|keeps?|maintains?|affirms?|unchanged|steady)|(?:avoids?|dodges?|spared|spares|no)\s+(?:a\s+)?downgrade",re.I)
def sentences(text):
    return re.split(r"(?<=[.!?])\s+(?=[A-Z])",re.sub(r"\s+"," ",text))
def assess(text):
    chosen=[s for s in sentences(text) if len(s)>35 and relevant.search(s)]
    if len(chosen)<4:return None
    # Cap each article to bound workflow time; truncate long sentences to model context.
    chosen=chosen[:40]
    results=analyser(chosen,truncation=True,max_length=512,batch_size=8)
    scores=[]
    for sentence,result in zip(chosen,results):
        label=result["label"].lower()
        # A rating affirmation is not an actual downgrade.
        if affirm.search(sentence):
            scores.append(0)
        else:
            scores.append({"negative":1,"neutral":0,"positive":-1}.get(label,0)*result["score"])
    return round(max(0,min(100,50+50*sum(scores)/len(scores))),1),len(chosen)

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
today=[x for x in NEWS.get("items",[]) if x.get("published_at_utc","")[:10]==DAY and " ".join(x.get("source","").casefold().split()) in APPROVED]
for item in today:
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
archive["method"]="Article-body financial sentiment v4: trafilatura extraction and ProsusAI/finbert on sovereign-risk-relevant sentences; higher = more negative tone. Not a news-shock or default-probability measure."
archive["checked_at_utc"]=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
archive["observations"]=[o for o in archive.get("observations",[]) if o["date"]!=DAY]
if len(articles)>=5:
    index=round(sum(a["score"] for a in articles)/len(articles),1)
    row={"date":DAY,"index":index,"article_count":len(articles),
         "headline_count":len(today),"coverage_pct":round(100*len(articles)/max(1,len(today)),1),
         "adverse_count":sum(a["score"]>55 for a in articles),
         "favourable_count":sum(a["score"]<45 for a in articles),
         "neutral_count":sum(45<=a["score"]<=55 for a in articles),
         "method_version":4,"articles":articles}
    archive["observations"].append(row)
    archive["observations"].sort(key=lambda x:x["date"])
    print("Full-text index",index,"from",len(articles),"of",len(today),"headlines")
else:
    print("Full-text coverage insufficient:",len(articles),"of",len(today),
          "— no score published")
archive["coverage"]={"date":DAY,"approved_headlines":len(today),"articles_analysed":len(articles),
                     "minimum_articles":5}
TARGET.write_text(json.dumps(archive,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

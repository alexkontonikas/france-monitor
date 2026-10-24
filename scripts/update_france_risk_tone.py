#!/usr/bin/env python3
"""Transparent headline-based daily France sovereign-risk tone (not full-text sentiment)."""
import datetime as dt
import json
import re
from pathlib import Path

SOURCE=Path("data/france-news.json")
TARGET=Path("data/france-risk-tone.json")
feed=json.loads(SOURCE.read_text(encoding="utf-8"))
# Phrase-level rules; the weights are a heuristic, not a trained probability model.
RISK={
 "downgrad":3,"default":4,"debt crisis":4,"fiscal crisis":4,"bond selloff":3,
 "bond sell-off":3,"yields surge":3,"yield spike":3,"spread widen":3,
 "political crisis":3,"government collapse":3,"no confidence":2,
 "confidence vote":1,"budget deadlock":3,"budget impasse":3,"deficit":1,
 "debt":1,"unrest":2,"riot":3,"violent":2,"violence":2,"protest":1,
 "strike":1,"turmoil":3,"instability":2,"resign":2,"snap election":2,
 "tax hike":1,"spending cuts":1,"austerity":2,"recession":2,
 "credit warning":2,"rating warning":2,"borrowing cost":2
}
RELIEF={
 "upgrade":3,"spread narrow":3,"yields fall":2,"bond rally":2,
 "fiscal consolidation":2,"deficit reduc":2,"deficit narrow":2,
 "budget approved":3,"budget passed":3,"deal reached":2,
 "confidence vote won":2,"stability restored":3,"growth accelerat":2,
 "debt reduc":2,"reform passed":2,"protests ease":2,"tensions ease":2
}
def score(headline):
    s=re.sub(r"\s+"," ",headline.lower())
    risk=sum(w for phrase,w in RISK.items() if phrase in s)
    relief=sum(w for phrase,w in RELIEF.items() if phrase in s)
    # Avoid classifying "no downgrade" as adverse.
    if "no downgrade" in s or "avoids downgrade" in s:risk=max(0,risk-3)
    return max(-4,min(4,risk-relief))

# Only observations published on the current UTC day, deduplicated by headline.
day=dt.datetime.now(dt.timezone.utc).date().isoformat()
headlines=[x for x in feed.get("items",[]) if x.get("published_at_utc","")[:10]==day]
unique={}
for item in headlines:
    key=re.sub(r"[^a-z0-9]+","",item["title"].lower())
    unique.setdefault(key,item)
headlines=list(unique.values())
scores=[score(x["title"]) for x in headlines]
if TARGET.exists():
    archive=json.loads(TARGET.read_text(encoding="utf-8"))
else:
    archive={"method":"Headline keyword/phrase heuristic v1; not article-text sentiment, not a probability of default","observations":[]}
if len(scores)>=3:
    # 50 is neutral; +4 maps to 100 and -4 to 0.
    value=round(50+12.5*sum(scores)/len(scores),1)
    observation={"date":day,"index":value,"headline_count":len(scores),
                 "adverse_count":sum(x>0 for x in scores),
                 "favourable_count":sum(x<0 for x in scores),
                 "neutral_count":sum(x==0 for x in scores)}
    archive["observations"]=[x for x in archive["observations"] if x["date"]!=day]
    archive["observations"].append(observation)
    archive["observations"].sort(key=lambda x:x["date"])
    archive["observations"]=archive["observations"][-730:]
    print("Risk-tone index",day,value,"headlines",len(scores))
else:
    print("Only",len(scores),"current-day headlines; preserving prior index")
archive["checked_at_utc"]=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
TARGET.write_text(json.dumps(archive,indent=2)+"\n",encoding="utf-8")

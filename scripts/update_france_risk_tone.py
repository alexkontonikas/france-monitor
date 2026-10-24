#!/usr/bin/env python3
"""Conservative event-based sovereign-risk NEWS CHANGE index.

Score new events, not negative vocabulary or the level of existing fiscal risks.
This version uses verified headline text only. Full articles are NOT claimed to be read.
"""
import datetime as dt
import json
import re
from pathlib import Path

SOURCE=Path("data/france-news.json")
TARGET=Path("data/france-risk-tone.json")
feed=json.loads(SOURCE.read_text(encoding="utf-8"))
day=dt.datetime.now(dt.timezone.utc).date().isoformat()

# An unchanged negative outlook is not a new negative rating action.
RATING_HOLD=re.compile(r"(moody.s|fitch|s&p|credit rating|rating).{0,90}(hold|held|keep|kept|maintain|affirm|unchanged|steady|spare|spared|avoid|dodge)|(?:avoid|dodge|spare|spared|no)\w*.{0,35}downgrad",re.I)
RATING_CUT=re.compile(r"(?:downgrad(?:e|ed|es)|cut(?:s)? (?:france.s )?(?:credit )?rating|rating (?:cut|lowered))",re.I)
RATING_UP=re.compile(r"(?:upgrad(?:e|ed|es)|rating raised)",re.I)
EVENTS=[
 ("rating_held",RATING_HOLD,0),
 ("rating_downgrade",RATING_CUT,3),
 ("rating_upgrade",RATING_UP,-3),
 ("budget_passed",re.compile(r"budget (?:passed|approved|adopted)|parliament (?:passes|approves) budget",re.I),-2),
 ("budget_rejected",re.compile(r"budget (?:rejected|defeated|blocked)|budget talks collapse|budget deal collapses",re.I),3),
 ("government_falls",re.compile(r"government (?:falls|collapses|toppled)|(?:loses|lost) (?:a )?no.confidence vote|prime minister resigns",re.I),3),
 ("government_survives",re.compile(r"(?:wins|survives) (?:a )?(?:confidence|no.confidence) vote",re.I),-2),
 ("bond_selloff",re.compile(r"(?:bond|oat) sell.off|(?:yield|spread)s? (?:surge|spike|jump|soar|hit (?:a )?(?:record|high))",re.I),2),
 ("bond_relief",re.compile(r"(?:bond|oat) rally|(?:yield|spread)s? (?:fall|drop|narrow|ease)",re.I),-2),
 ("unrest_escalates",re.compile(r"(?:violence|riots?) (?:flare|erupt|escalate|spread)|(?:violent|deadly) (?:clashes|protests)|(?:clashes|riots?) (?:flare|erupt)",re.I),2),
 ("unrest_eases",re.compile(r"(?:unrest|violence|protests?|riots?) (?:ease|subside|calm|end)",re.I),-2),
 ("fiscal_worsens",re.compile(r"deficit (?:widens|rises|surges)|debt (?:surges|jumps)|fiscal (?:forecast|outlook) (?:cut|worsens)",re.I),2),
 ("fiscal_improves",re.compile(r"deficit (?:narrows|falls|shrinks)|debt (?:falls|declines)|fiscal (?:forecast|outlook) improves",re.I),-2),
]
def classify(title):
    # Rating affirmation takes priority over mentions of downgrade.
    if RATING_HOLD.search(title):
        return "rating_held",0
    for event,pattern,weight in EVENTS[1:]:
        if pattern.search(title):
            return event,weight
    return None,None

today=[x for x in feed.get("items",[]) if x.get("published_at_utc","")[:10]==day]
# One event category per day; repeated reporting of the same event is not a new shock.
groups={}
for item in today:
    event,weight=classify(item.get("title",""))
    if event is None:continue
    groups.setdefault(event,{"weight":weight,"headlines":[]})["headlines"].append(item["title"])
# Moody's unchanged rating may be a positive surprise, but a headline alone does not
# establish market expectations: score 0 until expectation evidence is explicitly sourced.
events=[{"event":key,"score":v["weight"],"headline_count":len(v["headlines"]),
         "example_headline":v["headlines"][0]} for key,v in sorted(groups.items())]
archive=json.loads(TARGET.read_text(encoding="utf-8")) if TARGET.exists() else {"observations":[]}
archive["method"]="Event-based headline risk CHANGE index v2; deduplicated event categories, unclassified headlines excluded. Not full-article analysis."
archive["checked_at_utc"]=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
if len(events)>=2:
    # Equal-weighted event signals; zero denotes neutral. 50 +/- 12.5 per event-score point.
    index=round(max(0,min(100,50+12.5*sum(x["score"] for x in events)/len(events))),1)
    row={"date":day,"index":index,"event_count":len(events),"headline_count":len(today),
         "classified_headline_count":sum(x["headline_count"] for x in events),
         "adverse_count":sum(x["score"]>0 for x in events),
         "favourable_count":sum(x["score"]<0 for x in events),
         "neutral_count":sum(x["score"]==0 for x in events),
         "events":events,"method_version":2}
    archive["observations"]=[x for x in archive.get("observations",[]) if x["date"]!=day]
    archive["observations"].append(row)
    archive["observations"].sort(key=lambda x:x["date"])
    print("Event index:",index,"from",len(events),"event categories")
else:
    # Remove today's obsolete v1 result rather than display a misleading value.
    archive["observations"]=[x for x in archive.get("observations",[]) if x["date"]!=day]
    print("Insufficient independent event categories; no index published")
TARGET.write_text(json.dumps(archive,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

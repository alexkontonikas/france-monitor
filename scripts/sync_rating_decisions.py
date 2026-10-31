#!/usr/bin/env python3
"""Conservative automatic France sovereign ratings updater.

Google News is used for discovery, not as an authoritative ratings database.
Only matching, explicit agency/rating claims from at least two independent
trusted publishers can change a rating. Ambiguity leaves prior data unchanged.
"""
import datetime as dt
import email.utils
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

OUT=Path("data/ratings.json")
AGENCIES={
 "Moody's":{"rating":"Aa3","outlook":"Negative","last_review":"23 Oct 2026","next_review":"Not announced"},
 "S&P":{"rating":"A+","outlook":"Stable","last_review":"29 May 2026","next_review":"27 Nov 2026"},
 "Fitch":{"rating":"A+","outlook":"Stable","last_review":"28 Aug 2026","next_review":"Not announced"}
}
SCALES={"Moody's":["Baa3","Baa2","Baa1","A3","A2","A1","Aa3","Aa2","Aa1","Aaa"],
        "S&P":["BBB-","BBB","BBB+","A-","A","A+","AA-","AA","AA+","AAA"],
        "Fitch":["BBB-","BBB","BBB+","A-","A","A+","AA-","AA","AA+","AAA"]}
# Restrict auto-promotion to clear statements from recognised editorial sources.
TRUSTED={"Reuters","Financial Times","Bloomberg","Associated Press","AP News","Le Monde","France 24","Les Echos","Les Échos","Euronews","The Wall Street Journal","Wall Street Journal","Dow Jones"}
NAMES={"Moody's":r"moody(?:'|’)?s","S&P":r"(?:s&p|standard\s*(?:and|&)\s*poor(?:'|’)?s)","Fitch":r"fitch"}
ACTION=r"(?:downgrad(?:e|ed|es)|upgrad(?:e|ed|es)|cut(?:s)?|lower(?:s|ed)?|rais(?:e|ed|es)|affirm(?:s|ed)?|maintain(?:s|ed)?|keep(?:s|ing)?|kept|hold(?:s)?|held|retain(?:s|ed)?)"
now=dt.datetime.now(dt.timezone.utc)
if OUT.exists():
    data=json.loads(OUT.read_text())
    ratings=data.get("ratings",{})
else:
    ratings={}
for name,initial in AGENCIES.items(): ratings.setdefault(name,dict(initial))
events=data.get("events",[]) if OUT.exists() else []

def news(agency):
    q=f'France sovereign {agency} credit rating outlook downgrade upgrade affirmed'
    url="https://news.google.com/rss/search?"+urllib.parse.urlencode({"q":q,"hl":"en-GB","gl":"GB","ceid":"GB:en","when":"14d"})
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req,timeout=25) as response: root=ET.fromstring(response.read())
    result=[]
    for item in root.findall("./channel/item"):
        title=item.findtext("title","").strip()
        source=item.findtext("source","").strip()
        link=item.findtext("link","").strip()
        try: published=email.utils.parsedate_to_datetime(item.findtext("pubDate","")).astimezone(dt.timezone.utc)
        except (TypeError,ValueError): continue
        if (now-published).total_seconds()>14*86400 or published>now+dt.timedelta(hours=2):continue
        if source not in TRUSTED:continue
        result.append((title,source,link,published))
    return result

new_events=[]
for agency in AGENCIES:
    try: articles=news(agency)
    except Exception as exc:
        print(f"{agency}: feed unavailable ({exc}); keeping current rating")
        continue
    votes={}
    for title,source,link,published in articles:
        clean=title.rsplit(" - ",1)[0]
        if not re.search(r"\bfrance(?:'s)?\b|\bfrench\b",clean,re.I):continue
        if not re.search(NAMES[agency],clean,re.I):continue
        if not re.search(ACTION,clean,re.I):continue
        # Explicit rating must be associated with a rating action; ignore generic
        # stories listing old ratings or hypothetical future downgrades.
        if re.search(r"\b(?:could|may|might|would|risk|potential|expects?|forecast|if)\b",clean,re.I):continue
        candidates=re.findall(r"(?<![A-Za-z0-9])(?:Aaa|Aa[123]|A[123]|Baa[123]|Ba[123]|AAA|AA[+-]?|A[+-]?|BBB[+-]?)(?![A-Za-z0-9+-])",clean,re.I)
        candidates=[x for x in candidates if x in SCALES[agency]]
        if len(set(candidates))!=1:continue
        rating=candidates[0]
        # Require the explicit grade near the action word.
        action=re.search(ACTION,clean,re.I)
        grade=re.search(r"(?<![A-Za-z0-9])"+re.escape(rating)+r"(?![A-Za-z0-9+-])",clean)
        if not grade or abs(action.start()-grade.start())>95:continue
        key=(rating,published.date().isoformat())
        votes.setdefault(key,{})[source]={"title":title,"url":link}
    # Require two independent recognised publishers reporting same grade
    # on same UTC date; conflicting grades mean no automated update.
    qualified=[(key,proof) for key,proof in votes.items() if len(proof)>=2]
    if len({key[0] for key,_ in qualified})!=1:continue
    if not qualified:continue
    (rating,date),proof=max(qualified,key=lambda x:x[0][1])
    old=ratings[agency]["rating"]
    if old==rating:continue
    # Never infer a new outlook or next review date from a grade headline.
    ratings[agency].update({"rating":rating,"last_review":dt.date.fromisoformat(date).strftime("%d %b %Y"),"next_review":"Not announced"})
    new_events.append({"agency":agency,"previous_rating":old,"rating":rating,"date":date,
                       "sources":list(proof.values()),"verification":"two independent trusted news publishers; not official agency feed"})
    print(f"{agency}: {old} -> {rating} ({len(proof)} independent publishers)")

# Handle outlook-only actions independently of rating-grade changes.
def explicit_outlook(title, agency):
    clean=title.rsplit(" - ",1)[0]
    if not re.search(r"\bfrance(?:['’]s)?\b|\bfrench\b",clean,re.I): return None
    if not re.search(NAMES[agency],clean,re.I): return None
    if re.search(r"\b(?:could|may|might|would|potential|expects?|forecast|if)\b",clean,re.I): return None
    pattern=r"\b(?:revis(?:e|es|ed)|chang(?:e|es|ed)|lower(?:s|ed)?|cut(?:s)?|rais(?:e|es|ed)|upgrad(?:e|es|ed)|downgrad(?:e|es|ed))\b[^.;]{0,90}?\boutlook\b\s+to\s+['\"‘’“”]?(negative|stable|positive)\b"
    match=re.search(pattern,clean,re.I)
    return match.group(1).title() if match else None

for agency in AGENCIES:
    try: articles=news(agency)
    except Exception: continue
    votes={}
    for title,source,link,published in articles:
        outlook=explicit_outlook(title,agency)
        if outlook:
            publisher="Dow Jones" if source in {"The Wall Street Journal","Wall Street Journal","Dow Jones"} else source
            votes.setdefault((published.date().isoformat(),outlook),{})[publisher]={"title":title,"url":link}
    qualified=[(key,proof) for key,proof in votes.items() if len(proof)>=2]
    if not qualified: continue
    newest=max(key[0] for key,_ in qualified)
    matches=[(key,proof) for key,proof in qualified if key[0]==newest]
    if len(matches)!=1: continue
    (date,outlook),proof=matches[0]
    current=ratings[agency]
    previous_date=dt.datetime.strptime(current["last_review"],"%d %b %Y").date()
    if dt.date.fromisoformat(date)<previous_date or current.get("outlook")==outlook: continue
    old=current.get("outlook")
    current.update({"outlook":outlook,"last_review":dt.date.fromisoformat(date).strftime("%d %b %Y"),"next_review":"Not announced"})
    new_events.append({"agency":agency,"type":"outlook","previous_outlook":old,"outlook":outlook,"rating":current["rating"],"date":date,"sources":list(proof.values()),"verification":"two independent trusted news publishers; not official agency feed"})
    print(f"{agency}: outlook {old} -> {outlook}")

events=(events+new_events)[-50:]
OUT.parent.mkdir(exist_ok=True)
OUT.write_text(json.dumps({"checked_at_utc":now.isoformat(timespec="seconds"),"method":"corroborated editorial reports; fail-closed","ratings":ratings,"events":events},indent=2)+"\n")
print("Ratings checked; changes:",len(new_events))

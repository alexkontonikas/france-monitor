#!/usr/bin/env python3
"""Daily official AFT sovereign ratings check. Preserve last valid snapshot on failure."""
import datetime as dt
import json
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

URL = "https://www.aft.gouv.fr/en/frances-credit-ratings"
OUT = Path("data/ratings.json")
AGENCIES = {"Moody's": "Moody's", "Fitch": "Fitch", "Standard & Poor's": "S&P"}
class Tables(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables=[]; self.table=None; self.row=None; self.cell=None
    def handle_starttag(self, tag, attrs):
        if tag=="table": self.table=[]
        elif tag=="tr" and self.table is not None: self.row=[]
        elif tag in ("td","th") and self.row is not None: self.cell=[]
    def handle_data(self,data):
        if self.cell is not None: self.cell.append(data)
    def handle_endtag(self,tag):
        if tag in ("td","th") and self.cell is not None:
            self.row.append(" ".join("".join(self.cell).split())); self.cell=None
        elif tag=="tr" and self.row is not None:
            if self.row: self.table.append(self.row)
            self.row=None
        elif tag=="table" and self.table is not None:
            self.tables.append(self.table); self.table=None

def main():
    req=urllib.request.Request(URL,headers={"User-Agent":"Mozilla/5.0 (compatible; SovereignRiskResearch/1.0)"})
    with urllib.request.urlopen(req,timeout=30) as response:
        html=response.read().decode("utf-8","replace")
    parser=Tables(); parser.feed(html)
    records={}
    for table in parser.tables:
        for row in table:
            if len(row)<3: continue
            name=next((v for v in AGENCIES if row[0].lower().strip()==v.lower()),None)
            if not name: continue
            rating=row[1].strip().upper().replace(" ","")
            outlook=row[2].strip()
            if not re.fullmatch(r"(?:Aaa|Aa[1-3]|A[1-3]|Baa[1-3]|AAA|AA[+-]?|A[+-]?|BBB[+-]?)",rating,re.I): continue
            if outlook.lower() not in ("stable","negative","positive"): continue
            records[AGENCIES[name]]={"rating":rating,"outlook":outlook,"last_review":row[3] if len(row)>3 else None,"next_review":row[4] if len(row)>4 and row[4]!="-" else None}
    if len(records)!=3: raise ValueError("Official AFT table did not yield all three agencies; previous data preserved")
    previous=json.loads(OUT.read_text()) if OUT.exists() else {}
    changes=[]
    for agency,current in records.items():
        old=previous.get("ratings",{}).get(agency)
        if old and (old["rating"],old["outlook"])!=(current["rating"],current["outlook"]):
            changes.append({"agency":agency,"previous_rating":old["rating"],"rating":current["rating"],"previous_outlook":old["outlook"],"outlook":current["outlook"]})
    payload={"source":URL,"checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),"ratings":records,"latest_changes":changes}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("Verified AFT ratings:",json.dumps(records))
    if changes: print("RATING/OUTLOOK CHANGES:",json.dumps(changes))
if __name__=="__main__": main()

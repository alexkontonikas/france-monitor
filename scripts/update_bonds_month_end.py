#!/usr/bin/env python3
"""Create month-end aligned sovereign yields from Eurostat daily Maastricht series."""
import datetime as dt
import json
import urllib.parse
import urllib.request
from pathlib import Path
URL="https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/irt_lt_mcby_d"
start=f"{dt.date.today().year-5}-{dt.date.today().month:02d}-01"
params=[("geo",x) for x in ("FR","DE","IT","EL")]+[("sinceTimePeriod",start),("lang","EN")]
req=urllib.request.Request(URL+"?"+urllib.parse.urlencode(params),headers={"User-Agent":"FranceSovereignMonitor/1.0"})
with urllib.request.urlopen(req,timeout=90) as response: data=json.load(response)
dims=data["dimension"]; ids=data["id"]; sizes=data["size"]
def idx(dim,val):return dims[dim]["category"]["index"][val]
def lookup(geo,date):
    pos={"geo":geo,"time":date}; flat=0
    for name,size in zip(ids,sizes):
        if name in pos: n=idx(name,pos[name])
        elif size==1:n=0
        else:raise ValueError(f"Ambiguous Eurostat dimension {name}: {size}")
        flat=flat*size+n
    raw=data["value"]
    v=raw.get(str(flat)) if isinstance(raw,dict) else raw[flat]
    return float(v) if v is not None else None
times=sorted(dims["time"]["category"]["index"])
months={}
for day in times:
    if day<start:continue
    vals={code:lookup(geo,day) for code,geo in (("FR","FR"),("DE","DE"),("IT","IT"),("GR","EL"))}
    if all(v is not None and -5<v<30 for v in vals.values()):
        months[day[:7]]={"date":day,"month":day[:7],"yields_pct":vals}
# Exclude current unfinished calendar month from historical month-end data.
current=dt.date.today().strftime("%Y-%m")
rows=[months[k] for k in sorted(months) if k<current]
if len(rows)<45:raise ValueError(f"Insufficient aligned month-end points: {len(rows)}")
payload={"source":URL,"dataset":"irt_lt_mcby_d","frequency":"last common available daily observation in each completed calendar month","retrieved_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),"observations":rows}
out=Path("data/bonds-month-end.json");out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
print(f"Validated {len(rows)} month-end points: {rows[0]['date']} through {rows[-1]['date']}")

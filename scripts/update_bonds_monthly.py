#!/usr/bin/env python3
"""Backfill five years of monthly 10-year bond yields from Eurostat (JSON-stat)."""
import datetime as dt
import json
import urllib.parse
import urllib.request
from pathlib import Path

URL="https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/irt_lt_mcby_m"
today=dt.date.today()
start=f"{today.year-5}-{today.month:02d}"
params=[("geo",x) for x in ("FR","DE","IT","EL")]+[("sinceTimePeriod",start),("lang","EN")]
req=urllib.request.Request(URL+"?"+urllib.parse.urlencode(params),headers={"User-Agent":"FranceSovereignMonitor/1.0"})
with urllib.request.urlopen(req,timeout=45) as resp: data=json.load(resp)
ids=data["id"]
dims=data["dimension"]
sizes=data["size"]
def index(name,value):
    return dims[name]["category"]["index"][value]
def value_for(geo,period):
    coords={"geo":geo,"time":period}
    # Remaining dimensions must be singletons; reject ambiguous selections.
    flat=0
    for name,size in zip(ids,sizes):
        if name in coords: pos=index(name,coords[name])
        elif size==1: pos=0
        else: raise ValueError(f"Unexpected multi-valued dimension: {name}")
        flat=flat*size+pos
    raw=data["value"]
    v=raw.get(str(flat)) if isinstance(raw,dict) else raw[flat]
    return float(v) if v is not None else None
periods=sorted(dims["time"]["category"]["index"],key=lambda p:dims["time"]["category"]["index"][p])
rows=[]
for period in periods:
    if period<start:continue
    vals={code:value_for(geo,period) for code,geo in (("FR","FR"),("DE","DE"),("IT","IT"),("GR","EL"))}
    if all(v is not None and -5<v<30 for v in vals.values()):
        rows.append({"date":period,"yields_pct":vals})
rows=rows[-60:]\nif len(rows)<45:raise ValueError(f"Too few aligned historical monthly observations: {len(rows)}")
out=Path("data/bonds-monthly.json")
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps({"source":URL,"dataset":"irt_lt_mcby_m","frequency":"monthly averages","retrieved_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),"observations":rows},indent=2)+"\n")
print(f"Validated {len(rows)} monthly observations, {rows[0]['date']} to {rows[-1]['date']}")

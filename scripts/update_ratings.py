#!/usr/bin/env python3
"""Daily rating-decision news watch. Headlines are leads, never rating confirmations."""
import datetime as dt
import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

OUT=Path("data/ratings-watch.json")
QUERY='France sovereign (Moody\'s OR Fitch OR S&P) (rating OR downgrade OR outlook)'
url="https://news.google.com/rss/search?"+urllib.parse.urlencode({"q":QUERY,"hl":"en-GB","gl":"GB","ceid":"GB:en"})
req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
with urllib.request.urlopen(req,timeout=25) as r:
    root=ET.fromstring(r.read())
items=[]
for node in root.findall("./channel/item"):
    title=node.findtext("title","").strip()
    link=node.findtext("link","").strip()
    date=node.findtext("pubDate","").strip()
    if title and link: items.append({"title":title,"url":link,"published":date})
if not items: raise ValueError("No rating-news items returned; keeping prior snapshot")
OUT.parent.mkdir(exist_ok=True)
OUT.write_text(json.dumps({"checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),"source":"Google News RSS","status":"unverified leads; not agency decisions","items":items[:15]},indent=2)+"\n")
print("Ratings news watch collected",len(items),"headlines; rating figures remain unchanged pending confirmation")

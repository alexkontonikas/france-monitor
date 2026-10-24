#!/usr/bin/env python3
"""Fetch publicly displayed 10Y sovereign yields; never publish unverified quotes."""
import datetime as dt
import json
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

URL = "https://countryeconomy.com/bonds"
COUNTRIES = {"France": "FR", "Germany": "DE", "Italy": "IT", "Greece": "GR"}
OUT = Path("data/bonds.json")

class TableReader(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables, self.table, self.row, self.cell = [], None, None, None
    def handle_starttag(self, tag, attrs):
        if tag == "table": self.table = []
        elif self.table is not None and tag == "tr": self.row = []
        elif self.row is not None and tag in ("td", "th"): self.cell = []
    def handle_data(self, data):
        if self.cell is not None: self.cell.append(data)
    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            if self.row: self.table.append(self.row)
            self.row = None
        elif tag == "table" and self.table is not None:
            self.tables.append(self.table)
            self.table = None

def number(s):
    s = s.replace("%", "").replace("−", "-").strip()
    m = re.fullmatch(r"[-+]?\d{1,2}(?:[.,]\d{1,4})?", s)
    if not m: return None
    return float(s.replace(",", "."))

def main():
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0 (compatible; SovereignRiskResearch/1.0)"})
    with urllib.request.urlopen(req, timeout=25) as resp:
        html = resp.read().decode("utf-8", "replace")
    parser = TableReader()
    parser.feed(html)
    # Conservative parsing: require an explicit 10Y yield column and one country per row.
    quotes = {}
    for table in parser.tables:
        if not table: continue
        header = [x.lower() for x in table[0]]
        yieldcols = [i for i, h in enumerate(header) if h.strip() in ("yield", "10-year government bond yield", "10y yield")]
        if not yieldcols: continue
        for row in table[1:]:
            for country, code in COUNTRIES.items():
                if not any(re.match(r"^"+re.escape(country)+r"(?:\s|$)", c, flags=re.I) for c in row): continue
                for i in yieldcols:
                    if i < len(row):
                        v = number(row[i])
                        if v is not None and 0 < v < 25:
                            date_text = next((c for c in row if re.fullmatch(r"\d{2}/\d{2}/\d{4}", c)), None)
                            if not date_text: continue
                            # Source displays US-style dates (month/day/year).
                            observed = dt.datetime.strptime(date_text, "%m/%d/%Y").date()
                            age = (dt.datetime.now(dt.timezone.utc).date() - observed).days
                            if not (0 <= age <= 5): continue
                            quotes[code] = {"yield_pct": v, "country": country, "observation_date": observed.isoformat()}
    if len(quotes) != 4:
        raise ValueError("Source did not provide four recent, dated 10-year quotes; no update published.")
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    # The website does not guarantee synchronized quote timestamps.
    payload = {"source": URL, "retrieved_at_utc": now, "quote_time_verified": False,
               "frequency": "latest available public observations (not verified intraday)",
               "quotes": quotes}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + chr(10), encoding="utf-8")
    print("Updated verified table fields", now)

if __name__ == "__main__":
    main()

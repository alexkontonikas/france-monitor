import json,datetime,urllib.parse,urllib.request,pathlib
BASE="https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
S={"deficit":("gov_10dd_edpt1",{"unit":"PC_GDP","sector":"S13","na_item":"B9"}),"debt":("gov_10dd_edpt1",{"unit":"PC_GDP","sector":"S13","na_item":"GD"}),"interest":("gov_10dd_edpt1",{"unit":"PC_GDP","sector":"S13","na_item":"D41PAY"}),"nominal":("nama_10_gdp",{"unit":"CP_MEUR","na_item":"B1G"}),"gdp":("nama_10_gdp",{"unit":"CLV_PCH_PRE","na_item":"B1G"}),"inflation":("prc_hicp_aind",{"indic":"RCH_A","coicop":"CP00"}),"unemployment":("une_rt_a",{"unit":"PC_ACT","sex":"T","age":"TOTAL"}),"esi_fr":("ei_bssi_m_r2",{"indic":"BS-ESI-I","s_adj":"SA"}),"esi_ea20":("ei_bssi_m_r2",{"indic":"BS-ESI-I","s_adj":"SA"}),"esi_ea21":("ei_bssi_m_r2",{"indic":"BS-ESI-I","s_adj":"SA"})}
def read(ds,params):
 u=BASE+ds+"?"+urllib.parse.urlencode(params)
 with urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":"FranceMonitor/1.0"}),timeout=40) as response:j=json.load(response)
 ids=j["id"];sizes=j["size"];t=ids.index("time");out=[]
 for period,pos in j["dimension"]["time"]["category"]["index"].items():
  n=0
  for i,size in enumerate(sizes):n=n*size+(pos if i==t else 0)
  value=j.get("value",{}).get(str(n))
  if isinstance(value,(int,float)):out.append([period,value])
 return sorted(out)
path=pathlib.Path("data/debt-sustainability.json")
old=json.loads(path.read_text()) if path.exists() else {}
data=old.get("series",{}).copy();errors={}
for key,(ds,filters) in S.items():
 params=dict(filters,geo="EA21" if key=="esi_ea21" else "EA20" if key=="esi_ea20" else "FR",freq="M" if key.startswith("esi") else "A")
 try:
  rows=read(ds,params)
  if not rows:raise ValueError("Empty observations")
  data[key]=[[t,-v] for t,v in rows] if key=="deficit" else rows
  print(key,len(rows),rows[-1])
 except Exception as e:errors[key]=str(e);print("Unavailable",key,str(e))
ea=dict(data.get("esi_ea20",[]));ea.update(dict(data.get("esi_ea21",[])));data["esi_ea"]=sorted(ea.items())
d=dict(data.get("debt",[]));i=dict(data.get("interest",[]));n=dict(data.get("nominal",[]));rg=[]
for year,v in i.items():
 previous=str(int(year)-1)
 if previous in d and previous in n and year in n and d[previous] and n[previous]:
  growth=100*(n[year]/n[previous]-1)
  r=100*v*n[year]/(d[previous]*n[previous])
  rg.append([year,r-growth])
data["rg"]=rg
if not any(data.values()):raise SystemExit("No verified observations")
path.parent.mkdir(exist_ok=True)
path.write_text(json.dumps({"checked_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"series":data,"errors":errors},indent=2)+"\n")

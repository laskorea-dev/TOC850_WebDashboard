"""점촌 measure_logs_v2 원자료를 전 컬럼 그대로 수집해 data.json 에 저장한다.

TOC_Conc 만이 아니라 MSIG / SLOP / ICPT / DilutionFactor / FACT / OFST 를 같이
받아야 계측기 내부 공식을 검산할 수 있다. 대시보드 집계는 쓰지 않는다.
"""
import json
import urllib.request

from common import HERE, config, save

BASE, H = config()
FROM, TO = "2026-08-10", "2026-09-03"

rows, offset = [], 0
while True:
    h = dict(H)
    h["Range"] = f"{offset}-{offset+999}"
    url = (BASE + "/measure_logs_v2?Site_ID=eq.jeomchon"
           f"&Date_Time=gte.{FROM}&Date_Time=lt.{TO}"
           "&select=*&order=Date_Time.asc")
    batch = json.load(urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=90))
    rows += batch
    if len(batch) < 1000:
        break
    offset += 1000

print(f"{len(rows)}건  {rows[0]['Date_Time']} ~ {rows[-1]['Date_Time']}")
print("컬럼:", list(rows[0].keys()))
save(rows, "data.json")
print("saved →", HERE)

"""희석배수 · 교정상수 변경 이력 — 설정이 바뀐 시점만 뽑는다.

DF 를 바꾼 순간 표시값에 단차가 남는지 보는 것이 목적이다.
단차가 없으면 실제 물리 희석과 DF 설정이 같이 움직였다는 뜻이고,
희석기가 정상이며 TOC_Conc 가 이미 희석 보정된 값이라는 근거가 된다.
"""
import json
import urllib.request

from common import config

BASE, H = config()

rows, offset = [], 0
while True:
    h = dict(H)
    h["Range"] = f"{offset}-{offset+999}"
    url = (BASE + "/measure_logs_v2?Site_ID=eq.jeomchon"
           "&select=Date_Time,TOC_Conc,MSIG,DilutionFactor,SLOP,ICPT,FACT,OFST"
           "&order=Date_Time.asc")
    batch = json.load(urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=90))
    rows += batch
    if len(batch) < 1000:
        break
    offset += 1000

print(f"전체 {len(rows)}건  {rows[0]['Date_Time']} ~ {rows[-1]['Date_Time']}\n")

prev = None
for i, r in enumerate(rows):
    key = (r["DilutionFactor"], r["SLOP"], r["ICPT"], r["FACT"], r["OFST"])
    if key != prev:
        print(f"{r['Date_Time']}  DF={r['DilutionFactor']} SLOP={r['SLOP']} "
              f"ICPT={r['ICPT']} FACT={r['FACT']} OFST={r['OFST']}")
        if i:
            p = rows[i - 1]
            print(f"    직전 {p['Date_Time']}  TOC={p['TOC_Conc']} MSIG={p['MSIG']}")
        print(f"    직후 {r['Date_Time']}  TOC={r['TOC_Conc']} MSIG={r['MSIG']}")
        prev = key

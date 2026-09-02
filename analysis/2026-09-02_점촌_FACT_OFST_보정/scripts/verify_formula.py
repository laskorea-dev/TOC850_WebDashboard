"""계측기 공식 검산 — 그리고 저장 자료로는 적용 순서를 구분할 수 없다는 것의 확인.

두 후보:
    (가) TOC_Conc = (MSIG-ICPT)/SLOP * DF * FACT + OFST   ← OFST 가 희석 뒤
    (나) TOC_Conc = ((MSIG-ICPT)/SLOP * FACT + OFST) * DF ← OFST 가 희석 앞  ★ 실제

현장 확인 결과 (나) 가 맞다. 다만 이 자료 구간은 내내 FACT=1 / OFST=0 이라
두 식이 대수적으로 같아진다. 아래 검산이 양쪽 모두 0 불일치로 나오는 것이 그 증거다.
"검산이 통과했으니 순서가 맞다"고 말할 수 없다는 뜻이다.
"""
import collections

from common import load, raw

rows = load()
print(f"기간 {rows[0]['t']} ~ {rows[-1]['t']}  {len(rows)}건")
print("채널:", collections.Counter((r["Channel"], r["Channel_Name"]) for r in rows).most_common())
print("장비:", collections.Counter(r["Device_ID"] for r in rows).most_common())
for col in ("DilutionFactor", "SLOP", "ICPT", "FACT", "OFST"):
    print(f"  {col}:", collections.Counter(r[col] for r in rows).most_common(5))

bad_a = bad_b = 0
for r in rows:
    if None in (r["MSIG"], r["SLOP"], r["ICPT"], r["TOC_Conc"], r["DilutionFactor"]):
        continue
    f, o, df = (r["FACT"] or 1.0), (r["OFST"] or 0.0), r["DilutionFactor"]
    a = raw(r) * df * f + o
    b = (raw(r) * f + o) * df
    bad_a += abs(a - r["TOC_Conc"]) > 0.02
    bad_b += abs(b - r["TOC_Conc"]) > 0.02
print(f"\n(가) 불일치 {bad_a} / {len(rows)}건")
print(f"(나) 불일치 {bad_b} / {len(rows)}건")
print("둘 다 0 이면 이 구간 자료로는 순서를 판별할 수 없다는 뜻이다.")

print("\n순서가 갈리는 지점 — OFST 를 넣으면 표시값이 DF 배로 증폭된다")
r = rows[len(rows) // 2]
print(f"  예시 {r['Date_Time']}  희석전값={raw(r):.3f}  DF=×{r['DilutionFactor']:.0f}")
for f, o in [(0.55, 0.0), (0.55, -0.5), (0.55, +1.0)]:
    a = raw(r) * r["DilutionFactor"] * f + o
    b = (raw(r) * f + o) * r["DilutionFactor"]
    print(f"    FACT={f} OFST={o:+.1f}  → (가) {a:7.2f}   (나) {b:7.2f}   차이 {b-a:+.2f}")

# 일자별 요약 — 8/29 단차 확인용
by_day = collections.defaultdict(list)
for r in rows:
    if r["TOC_Conc"] is not None:
        by_day[r["t"].date()].append(r["TOC_Conc"])
print("\n일자별 (건수 / 최소 / 중앙 / 최대)")
for d in sorted(by_day):
    v = sorted(by_day[d])
    print(f"  {d}  {len(v):3d}  {v[0]:6.1f} {v[len(v)//2]:6.1f} {v[-1]:6.1f}")

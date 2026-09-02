"""계측기 내부 공식 검산 — FACT 를 희석배수 앞에 놓을지 뒤에 놓을지 확정한다.

    TOC_Conc = (MSIG - ICPT) / SLOP * DilutionFactor * FACT + OFST

이 식이 맞으면 DF 가 먼저 곱해지고 FACT 가 그 뒤에 붙는다는 뜻이고,
표시값이 이미 희석 보정된 값이므로 FACT 는 희석배수와 무관하게 얹으면 된다.
"""
import collections

from common import load

rows = load()
print(f"기간 {rows[0]['t']} ~ {rows[-1]['t']}  {len(rows)}건")
print("채널:", collections.Counter((r["Channel"], r["Channel_Name"]) for r in rows).most_common())
print("장비:", collections.Counter(r["Device_ID"] for r in rows).most_common())
for col in ("DilutionFactor", "SLOP", "ICPT", "FACT", "OFST"):
    print(f"  {col}:", collections.Counter(r[col] for r in rows).most_common(5))

bad = 0
for r in rows:
    if None in (r["MSIG"], r["SLOP"], r["ICPT"], r["TOC_Conc"], r["DilutionFactor"]):
        continue
    calc = ((r["MSIG"] - r["ICPT"]) / r["SLOP"]
            * r["DilutionFactor"] * (r["FACT"] or 1.0) + (r["OFST"] or 0.0))
    if abs(calc - r["TOC_Conc"]) > 0.02:
        bad += 1
        if bad <= 5:
            print("  불일치", r["Date_Time"], f"계산={calc:.3f} 저장={r['TOC_Conc']:.3f}")
print(f"\n공식 불일치 {bad} / {len(rows)}건")

# 일자별 요약 — 8/29 단차 확인용
by_day = collections.defaultdict(list)
for r in rows:
    if r["TOC_Conc"] is not None:
        by_day[r["t"].date()].append(r["TOC_Conc"])
print("\n일자별 (건수 / 최소 / 중앙 / 최대)")
for d in sorted(by_day):
    v = sorted(by_day[d])
    print(f"  {d}  {len(v):3d}  {v[0]:6.1f} {v[len(v)//2]:6.1f} {v[-1]:6.1f}")

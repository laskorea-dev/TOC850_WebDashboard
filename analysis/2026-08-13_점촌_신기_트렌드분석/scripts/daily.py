import json, os, sys, math, collections, datetime as dt
sys.stdout.reconfigure(encoding="utf-8")
here = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(here, "data.json"), encoding="utf-8"))
WD = "월화수목금토일"


def load(site, chname):
    seen, out = set(), []
    for r in D[site]:
        if r["Channel_Name"] != chname or r["Date_Time"] in seen:
            continue
        seen.add(r["Date_Time"])
        out.append((dt.datetime.fromisoformat(r["Date_Time"]), r["TOC_Conc"]))
    out.sort()
    return out


for label, site, ch, lo, hi in [
    ("점촌 원수", "jeomchon", "원수", "2026-08-05", "2026-08-13"),
    ("신기 유입수", "Shingi", "유입수", "2026-08-05", "2026-08-13"),
]:
    rows = [(t, v) for t, v in load(site, ch) if lo <= t.strftime("%Y-%m-%d") <= hi]
    print("=" * 78)
    print(label)
    byd = collections.defaultdict(list)
    for t, v in rows:
        byd[t.date()].append((t, v))
    print(f"{'날짜':<12}{'요일':<4}{'n':>4}{'평균':>9}{'중앙':>9}{'최대':>9}{'주간08-18':>11}{'야간22-04':>11}{'주/야비':>8}")
    for d in sorted(byd):
        v = [x for _, x in byd[d]]
        day = [x for t, x in byd[d] if 8 <= t.hour < 18]
        nig = [x for t, x in byd[d] if t.hour >= 22 or t.hour < 4]
        dm = sum(day) / len(day) if day else float("nan")
        nm = sum(nig) / len(nig) if nig else float("nan")
        ratio = dm / nm if nm else float("inf")
        print(f"{d}  {WD[d.weekday()]:<4}{len(v):>4}{sum(v)/len(v):>9.1f}"
              f"{sorted(v)[len(v)//2]:>9.1f}{max(v):>9.1f}{dm:>11.1f}{nm:>11.1f}{ratio:>8.1f}")

    # 요일별
    byw = collections.defaultdict(list)
    for t, v in rows:
        byw[t.weekday()].append(v)
    print("  요일별 평균:", "  ".join(f"{WD[w]}={sum(x)/len(x):.0f}" for w, x in sorted(byw.items())))

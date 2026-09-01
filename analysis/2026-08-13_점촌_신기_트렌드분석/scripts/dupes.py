import json, os, sys, collections, datetime as dt
sys.stdout.reconfigure(encoding="utf-8")
here = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(here, "data.json"), encoding="utf-8"))

for site, rows in D.items():
    print("=" * 70, site)
    by_t = collections.defaultdict(list)
    for r in rows:
        by_t[r["Date_Time"]].append(r)
    dup = {k: v for k, v in by_t.items() if len(v) > 1}
    print("고유 시각:", len(by_t), "· 중복 시각:", len(dup))
    if dup:
        # 중복끼리 값이 같은가?
        same = sum(1 for v in dup.values() if len({x["TOC_Conc"] for x in v}) == 1)
        print("  값까지 동일한 중복:", same, "/", len(dup))
        ks = sorted(dup)[:3]
        for k in ks:
            print("  예:", k, [(x["TOC_Conc"], x["DilutionFactor"], x["created_at"][:19]) for x in dup[k]])
        # 중복 시각의 시간 범위
        print("  중복 구간:", min(dup), "~", max(dup))

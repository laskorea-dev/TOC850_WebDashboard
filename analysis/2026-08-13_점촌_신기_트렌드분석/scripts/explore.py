import json, os, sys, collections, datetime as dt
sys.stdout.reconfigure(encoding="utf-8")
here = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(here, "data.json"), encoding="utf-8"))


def ts(s):
    return dt.datetime.fromisoformat(s)


for site, rows in D.items():
    print("=" * 70)
    print(site, len(rows), "건")
    for r in rows:
        r["t"] = ts(r["Date_Time"])
    rows.sort(key=lambda r: r["t"])

    # 채널별
    by_ch = collections.defaultdict(list)
    for r in rows:
        by_ch[(r["Channel"], r["Channel_Name"])].append(r)
    for k, v in by_ch.items():
        vals = [x["TOC_Conc"] for x in v if x["TOC_Conc"] is not None]
        print(f"  ch{k}: {len(v)}건  {v[0]['t']} ~ {v[-1]['t']}")
        if vals:
            sv = sorted(vals)
            print(f"     min={min(vals):.3f} p50={sv[len(sv)//2]:.3f} max={max(vals):.3f} mean={sum(vals)/len(vals):.3f}")

    # 월별 건수
    m = collections.Counter(r["t"].strftime("%Y-%m") for r in rows)
    print("  월별:", dict(sorted(m.items())))

    # 샘플 간격 분포
    gaps = collections.Counter()
    for a, b in zip(rows, rows[1:]):
        g = (b["t"] - a["t"]).total_seconds() / 60
        gaps[round(g)] += 1
    print("  간격(분) 상위:", gaps.most_common(8))

    # 희석배수
    print("  DilutionFactor:", collections.Counter(r["DilutionFactor"] for r in rows).most_common(5))
    print("  Device:", collections.Counter(r["Device_ID"] for r in rows).most_common())

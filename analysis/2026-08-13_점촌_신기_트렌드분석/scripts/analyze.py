import json, os, sys, math, collections, datetime as dt
sys.stdout.reconfigure(encoding="utf-8")
here = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(here, "data.json"), encoding="utf-8"))

SERIES = [
    ("점촌하수처리장", "jeomchon", "원수"),
    ("신기폐수처리장", "Shingi", "유입수"),
    ("신기폐수처리장", "Shingi", "effluent"),
]


def load(site, chname):
    seen, out = set(), []
    for r in D[site]:
        if r["Channel_Name"] != chname:
            continue
        if r["Date_Time"] in seen:
            continue
        seen.add(r["Date_Time"])
        out.append((dt.datetime.fromisoformat(r["Date_Time"]), r["TOC_Conc"], r["DilutionFactor"]))
    out.sort()
    return out


def quant(v, q):
    s = sorted(v)
    if not s:
        return float("nan")
    i = q * (len(s) - 1)
    lo = int(math.floor(i))
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (i - lo)


def stats(v):
    n = len(v)
    m = sum(v) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in v) / (n - 1)) if n > 1 else 0
    return dict(n=n, mean=m, sd=sd, cv=sd / m if m else float("nan"),
                min=min(v), p25=quant(v, .25), p50=quant(v, .5), p75=quant(v, .75),
                p95=quant(v, .95), max=max(v))


def acf(x, lag):
    n = len(x)
    if lag >= n:
        return float("nan")
    m = sum(x) / n
    den = sum((a - m) ** 2 for a in x)
    num = sum((x[i] - m) * (x[i + lag] - m) for i in range(n - lag))
    return num / den if den else float("nan")


report = {}
for label, site, ch in SERIES:
    rows = load(site, ch)
    key = f"{label}/{ch}"
    print("=" * 74)
    print(f"{key}   {len(rows)}건   {rows[0][0]} ~ {rows[-1][0]}")

    vals = [v for _, v, _ in rows if v is not None]
    s = stats(vals)
    print(f"  전체: mean={s['mean']:.1f} sd={s['sd']:.1f} CV={s['cv']:.2f} "
          f"min={s['min']:.1f} p25={s['p25']:.1f} p50={s['p50']:.1f} p75={s['p75']:.1f} p95={s['p95']:.1f} max={s['max']:.1f}")

    # 0값 비율
    z = sum(1 for v in vals if v == 0)
    print(f"  0.00 값: {z}건 ({z/len(vals)*100:.1f}%)")

    # 희석배수 구간
    seg = []
    for t, v, d in rows:
        if not seg or seg[-1][0] != d:
            seg.append([d, t, t, 0])
        seg[-1][2] = t
        seg[-1][3] += 1
    print("  희석배수 구간:", [(f"x{d:g}", a.strftime('%m-%d %H:%M'), b.strftime('%m-%d %H:%M'), n) for d, a, b, n in seg][:8])

    # 연속 구간 (6시간 이상 끊기면 분리)
    segs, cur = [], [rows[0]]
    for a, b in zip(rows, rows[1:]):
        if (b[0] - a[0]).total_seconds() > 6 * 3600:
            segs.append(cur); cur = [b]
        else:
            cur.append(b)
    segs.append(cur)
    segs = [g for g in segs if len(g) >= 96]  # 하루 이상
    print(f"  연속 구간(1일↑): {len(segs)}개")
    for g in segs:
        print(f"     {g[0][0]:%Y-%m-%d %H:%M} ~ {g[-1][0]:%Y-%m-%d %H:%M}  {len(g)}건 "
              f"({(g[-1][0]-g[0][0]).total_seconds()/86400:.1f}일)")

    # 시간대별 프로파일 (가장 긴 연속 구간)
    if segs:
        g = max(segs, key=len)
        byh = collections.defaultdict(list)
        for t, v, _ in g:
            if v is not None:
                byh[t.hour].append(v)
        prof = {h: sum(x) / len(x) for h, x in sorted(byh.items())}
        gm = sum(prof.values()) / len(prof)
        print(f"  시간대별 평균 (구간 {g[0][0]:%m-%d}~{g[-1][0]:%m-%d}, 전체평균 {gm:.1f}):")
        line = "     "
        for h in range(24):
            if h in prof:
                line += f"{h:02d}h={prof[h]:7.1f}({prof[h]/gm*100:5.0f}%)  "
                if h % 4 == 3:
                    line += "\n     "
        print(line)
        hi = max(prof, key=prof.get); lo = min(prof, key=prof.get)
        print(f"  → 최고 {hi:02d}시 {prof[hi]:.1f} / 최저 {lo:02d}시 {prof[lo]:.1f} "
              f"· 진폭비 {prof[hi]/prof[lo] if prof[lo] else float('inf'):.2f}배 "
              f"· 일변동폭 {(max(prof.values())-min(prof.values()))/gm*100:.0f}% of mean")

        # 자기상관 — 15분 간격 균등 그리드로 리샘플
        t0 = g[0][0]
        grid = {}
        for t, v, _ in g:
            grid[round((t - t0).total_seconds() / 900)] = v
        span = max(grid)
        x = []
        for i in range(span + 1):
            if i in grid:
                x.append(grid[i])
            else:
                x.append(None)
        # 선형보간
        idx = [i for i, v in enumerate(x) if v is not None]
        for i in range(len(x)):
            if x[i] is None:
                lo_ = max([j for j in idx if j < i], default=None)
                hi_ = min([j for j in idx if j > i], default=None)
                if lo_ is None or hi_ is None:
                    x[i] = x[lo_] if lo_ is not None else x[hi_]
                else:
                    x[i] = x[lo_] + (x[hi_] - x[lo_]) * (i - lo_) / (hi_ - lo_)
        print(f"  자기상관 (결측보간 후 {len(x)}포인트 = {len(x)*15/60/24:.1f}일):")
        for hours in [1, 3, 6, 8, 12, 18, 24, 36, 48, 72]:
            lag = int(hours * 4)
            r = acf(x, lag)
            bar = "#" * max(0, int(round(r * 30))) if r == r and r > 0 else ""
            print(f"     {hours:3d}시간(lag{lag:4d}): r={r:+.3f} {bar}")

    report[key] = dict(stats=s, n=len(rows))

print()
print("=" * 74)
print("두 지점 비교 (겹치는 기간 2026-08-05 ~ 08-13, 유입 계열)")
a = {t: v for t, v, _ in load("jeomchon", "원수")}
b = {t: v for t, v, _ in load("Shingi", "유입수")}
lo = max(min(a), min(b)); hi_ = min(max(a), max(b))
av = [v for t, v in a.items() if lo <= t <= hi_]
bv = [v for t, v in b.items() if lo <= t <= hi_]
print(f"  기간 {lo:%m-%d %H:%M} ~ {hi_:%m-%d %H:%M}")
for nm, v in (("점촌 원수", av), ("신기 유입수", bv)):
    s = stats(v)
    print(f"  {nm:10s} n={s['n']:4d} mean={s['mean']:8.1f} p50={s['p50']:8.1f} max={s['max']:8.1f} CV={s['cv']:.2f}")

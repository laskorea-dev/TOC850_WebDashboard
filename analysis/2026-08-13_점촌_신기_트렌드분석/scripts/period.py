import json, os, sys, math, cmath, collections, datetime as dt
sys.stdout.reconfigure(encoding="utf-8")
here = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(here, "data.json"), encoding="utf-8"))
WD = "월화수목금토일"


def load(site, ch):
    seen, out = set(), []
    for r in D[site]:
        if r["Channel_Name"] != ch or r["Date_Time"] in seen:
            continue
        seen.add(r["Date_Time"])
        out.append((dt.datetime.fromisoformat(r["Date_Time"]), r["TOC_Conc"]))
    return sorted(out)


def segments(rows, gap_h=6, min_pts=96):
    segs, cur = [], [rows[0]]
    for a, b in zip(rows, rows[1:]):
        if (b[0] - a[0]).total_seconds() > gap_h * 3600:
            segs.append(cur); cur = [b]
        else:
            cur.append(b)
    segs.append(cur)
    return [s for s in segs if len(s) >= min_pts]


def grid15(seg):
    """15분 균등 격자로 리샘플 + 선형보간"""
    t0 = seg[0][0]
    g = {}
    for t, v in seg:
        g[round((t - t0).total_seconds() / 900)] = v
    n = max(g) + 1
    x = [g.get(i) for i in range(n)]
    idx = [i for i, v in enumerate(x) if v is not None]
    for i in range(n):
        if x[i] is None:
            lo = max([j for j in idx if j < i], default=None)
            hi = min([j for j in idx if j > i], default=None)
            if lo is None: x[i] = x[hi]
            elif hi is None: x[i] = x[lo]
            else: x[i] = x[lo] + (x[hi] - x[lo]) * (i - lo) / (hi - lo)
    return t0, x


def movavg(x, w):
    """중심 이동평균 (w는 홀수 아니어도 됨)"""
    n, half = len(x), w // 2
    out = []
    for i in range(n):
        a, b = max(0, i - half), min(n, i + half + 1)
        out.append(sum(x[a:b]) / (b - a))
    return out


def acf(x, lag):
    n = len(x); m = sum(x) / n
    den = sum((a - m) ** 2 for a in x)
    if not den or lag >= n: return 0.0
    return sum((x[i] - m) * (x[i + lag] - m) for i in range(n - lag)) / den


def periodogram(x, dt_min=15):
    """단순 DFT 파워. 주기(시간) → 파워"""
    n = len(x)
    m = sum(x) / n
    y = [v - m for v in x]
    # 해닝 창
    y = [y[i] * (0.5 - 0.5 * math.cos(2 * math.pi * i / (n - 1))) for i in range(n)]
    res = []
    for k in range(1, n // 2):
        s = sum(y[i] * cmath.exp(-2j * math.pi * k * i / n) for i in range(n))
        per_h = n * dt_min / 60 / k
        if 0.5 <= per_h <= 60:
            res.append((per_h, abs(s) ** 2))
    tot = sum(p for _, p in res) or 1
    return [(round(p, 2), pw / tot * 100) for p, pw in res]


for label, site, ch in [("점촌 원수", "jeomchon", "원수"), ("신기 유입수", "Shingi", "유입수")]:
    rows = load(site, ch)
    print("=" * 78)
    print(label)
    for seg in segments(rows):
        t0, x = grid15(seg)
        days = len(x) * 15 / 60 / 24
        if days < 2:
            continue
        print(f"\n▶ 구간 {t0:%Y-%m-%d %H:%M} ~ {t0 + dt.timedelta(minutes=15*(len(x)-1)):%m-%d %H:%M}  "
              f"{len(x)}포인트 ({days:.1f}일)")

        # 24시간 이동평균으로 추세 제거
        tr = movavg(x, 96)
        dtr = [a - b for a, b in zip(x, tr)]
        rng = max(x) - min(x)
        amp = max(dtr) - min(dtr)
        print(f"   원신호 진폭 {rng:.1f} · 추세제거 후 진폭 {amp:.1f} "
              f"· 추세(24h이동평균) 변동폭 {max(tr)-min(tr):.1f}")

        print("   자기상관        원신호 / 추세제거")
        for h in [6, 12, 18, 24, 36, 48]:
            lag = int(h * 4)
            if lag >= len(x): continue
            print(f"     {h:3d}h  r = {acf(x,lag):+.3f} / {acf(dtr,lag):+.3f}")

        # 주기도 상위
        pg = periodogram(dtr)
        top = sorted(pg, key=lambda p: -p[1])[:6]
        print("   주기도 상위(추세제거):", ", ".join(f"{p:.1f}h({pw:.1f}%)" for p, pw in top))

        # 일별 최소·최대 시각 일관성
        byd = collections.defaultdict(list)
        for i, v in enumerate(dtr):
            t = t0 + dt.timedelta(minutes=15 * i)
            byd[t.date()].append((t, v))
        mins, maxs = [], []
        for d, arr in sorted(byd.items()):
            if len(arr) < 80: continue
            mn = min(arr, key=lambda a: a[1]); mx = max(arr, key=lambda a: a[1])
            mins.append(mn[0].hour + mn[0].minute / 60)
            maxs.append(mx[0].hour + mx[0].minute / 60)
        if mins:
            def circ(hs):
                a = [h / 24 * 2 * math.pi for h in hs]
                c = sum(math.cos(t) for t in a) / len(a)
                s = sum(math.sin(t) for t in a) / len(a)
                mean_h = (math.atan2(s, c) % (2 * math.pi)) / (2 * math.pi) * 24
                R = math.hypot(c, s)
                return mean_h, R
            mh, mr = circ(mins); xh, xr = circ(maxs)
            print(f"   일별 최저 시각: {[f'{h:.1f}' for h in mins]}")
            print(f"     → 평균 {mh:04.1f}시, 집중도 R={mr:.2f} (1=완전히 같은 시각, 0=무작위)")
            print(f"   일별 최고 시각: {[f'{h:.1f}' for h in maxs]}")
            print(f"     → 평균 {xh:04.1f}시, 집중도 R={xr:.2f}")

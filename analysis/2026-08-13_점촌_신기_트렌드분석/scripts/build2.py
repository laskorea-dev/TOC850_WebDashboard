import json, os, sys, math, cmath, collections, datetime as dt
sys.stdout.reconfigure(encoding="utf-8")
here = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(here, "data.json"), encoding="utf-8"))
P = json.load(open(os.path.join(here, "payload.json"), encoding="utf-8"))
T0 = dt.datetime(2026, 8, 5, 0, 0)


def load(site, ch):
    seen, out = set(), []
    for r in D[site]:
        if r["Channel_Name"] != ch or r["Date_Time"] in seen:
            continue
        seen.add(r["Date_Time"])
        out.append((dt.datetime.fromisoformat(r["Date_Time"]), r["TOC_Conc"]))
    return sorted(x for x in out if x[0] >= T0)


def grid15(seg):
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
            x[i] = x[hi] if lo is None else x[lo] if hi is None else \
                x[lo] + (x[hi] - x[lo]) * (i - lo) / (hi - lo)
    return t0, x


def movavg(x, w):
    n, half = len(x), w // 2
    return [sum(x[max(0, i - half):min(n, i + half + 1)]) / (min(n, i + half + 1) - max(0, i - half))
            for i in range(n)]


def acf(x, lag):
    n = len(x); m = sum(x) / n
    den = sum((a - m) ** 2 for a in x)
    return sum((x[i] - m) * (x[i + lag] - m) for i in range(n - lag)) / den if den and lag < n else 0.0


def periodogram(x, dt_min=15):
    n = len(x); m = sum(x) / n
    y = [(v - m) * (0.5 - 0.5 * math.cos(2 * math.pi * i / (n - 1))) for i, v in enumerate(x)]
    res = []
    for k in range(1, n // 2):
        per = n * dt_min / 60 / k
        if 3 <= per <= 48:
            s = sum(y[i] * cmath.exp(-2j * math.pi * k * i / n) for i in range(n))
            res.append((per, abs(s) ** 2))
    tot = sum(p for _, p in res) or 1
    return [[round(p, 2), round(pw / tot * 100, 3)] for p, pw in sorted(res)]


def circR(hs):
    a = [h / 24 * 2 * math.pi for h in hs]
    c = sum(math.cos(t) for t in a) / len(a)
    s = sum(math.sin(t) for t in a) / len(a)
    return ((math.atan2(s, c) % (2 * math.pi)) / (2 * math.pi) * 24, math.hypot(c, s))


out = {}
for key, site, ch in [("jeomchon", "jeomchon", "원수"), ("shingi", "Shingi", "유입수")]:
    rows = load(site, ch)
    t0, x = grid15(rows)
    tr = movavg(x, 96)
    dtr = [a - b for a, b in zip(x, tr)]

    # 일별 편차 곡선 (하루 96포인트) — 완전한 날만
    byd = collections.defaultdict(dict)
    for i, v in enumerate(dtr):
        t = t0 + dt.timedelta(minutes=15 * i)
        byd[t.date()][t.hour * 4 + t.minute // 15] = round(v, 1)
    daily = []
    mins = []
    for d in sorted(byd):
        slots = byd[d]
        if len(slots) < 88:
            continue
        curve = [slots.get(s) for s in range(96)]
        daily.append(dict(d=d.strftime("%m-%d"), w="월화수목금토일"[d.weekday()], v=curve))
        got = [(s, v) for s, v in slots.items() if v is not None]
        mn = min(got, key=lambda a: a[1])
        mins.append(mn[0] / 4)
    mh, mr = circR(mins)

    # 평균 편차 프로파일 (시간별)
    prof = collections.defaultdict(list)
    for i, v in enumerate(dtr):
        prof[(t0 + dt.timedelta(minutes=15 * i)).hour].append(v)
    hprof = [round(sum(prof[h]) / len(prof[h]), 1) for h in range(24)]

    out[key] = dict(
        daily=daily,
        hprof=hprof,
        minHours=[round(h, 1) for h in mins],
        minMean=round(mh, 1), minR=round(mr, 2),
        acf=[[h, round(acf(dtr, int(h * 4)), 3)] for h in
             [1, 2, 3, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 30, 36, 42, 48, 60, 72]],
        pgram=periodogram(dtr),
        amp=round(max(hprof) - min(hprof), 1),
        trendRange=round(max(tr) - min(tr), 1),
    )
    top = sorted(out[key]["pgram"], key=lambda p: -p[1])[:3]
    print(key, "최저시각 평균", mh, "R", round(mr, 2), "| 편차진폭", out[key]["amp"],
          "| 주기도 top", top, "| 일수", len(daily))

P["detrend"] = out
with open(os.path.join(here, "payload.json"), "w", encoding="utf-8") as f:
    json.dump(P, f, ensure_ascii=False)
print("saved")

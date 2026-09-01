import json, os, sys, math, collections, datetime as dt
sys.stdout.reconfigure(encoding="utf-8")
here = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(here, "data.json"), encoding="utf-8"))
WD = "월화수목금토일"
T0 = dt.datetime(2026, 8, 5, 0, 0)


def load(site, ch):
    seen, out = set(), []
    for r in D[site]:
        if r["Channel_Name"] != ch or r["Date_Time"] in seen:
            continue
        seen.add(r["Date_Time"])
        out.append((dt.datetime.fromisoformat(r["Date_Time"]), r["TOC_Conc"]))
    return sorted(out)


def window(rows):
    return [(t, v) for t, v in rows if t >= T0]


J = window(load("jeomchon", "원수"))
S = window(load("Shingi", "유입수"))


def series(rows):
    return [[round((t - T0).total_seconds() / 60), round(v, 2)] for t, v in rows]


def hourly(rows):
    b = collections.defaultdict(list)
    for t, v in rows:
        b[t.hour].append(v)
    return [round(sum(b[h]) / len(b[h]), 1) if b.get(h) else None for h in range(24)]


def weekday(rows):
    b = collections.defaultdict(list)
    for t, v in rows:
        b[t.weekday()].append(v)
    return [round(sum(b[w]) / len(b[w]), 1) if b.get(w) else None for w in range(7)]


def acf(x, lag):
    n = len(x); m = sum(x) / n
    den = sum((a - m) ** 2 for a in x)
    return sum((x[i] - m) * (x[i + lag] - m) for i in range(n - lag)) / den if den else 0


def resample(rows):
    g = {}
    for t, v in rows:
        g[round((t - rows[0][0]).total_seconds() / 900)] = v
    out, last = [], rows[0][1]
    for i in range(max(g) + 1):
        last = g.get(i, last)
        out.append(last)
    return out


def acurve(rows):
    x = resample(rows)
    return [[h, round(acf(x, int(h * 4)), 3)] for h in [1, 2, 3, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 30, 36, 42, 48, 60, 72]]


def stat(rows):
    v = [x for _, x in rows]
    n = len(v); m = sum(v) / n
    sd = math.sqrt(sum((a - m) ** 2 for a in v) / (n - 1))
    s = sorted(v)
    return dict(n=n, mean=round(m, 1), sd=round(sd, 1), cv=round(sd / m, 2),
                p50=round(s[n // 2], 1), max=round(max(v), 1), min=round(min(v), 1))


def daynight(rows):
    b = collections.defaultdict(lambda: ([], []))
    for t, v in rows:
        d = t.date()
        if 8 <= t.hour < 18:
            b[d][0].append(v)
        elif t.hour >= 22 or t.hour < 4:
            b[d][1].append(v)
    out = []
    for d in sorted(b):
        day, nig = b[d]
        if len(day) < 8 or len(nig) < 8:
            continue
        dm, nm = sum(day) / len(day), sum(nig) / len(nig)
        out.append(dict(d=d.strftime("%m-%d"), w=WD[d.weekday()], day=round(dm, 1),
                        night=round(nm, 1), ratio=round(dm / nm, 1) if nm else None))
    return out


payload = dict(
    t0=T0.strftime("%Y-%m-%d"),
    ts=dict(jeomchon=series(J), shingi=series(S)),
    hourly=dict(jeomchon=hourly(J), shingi=hourly(S)),
    weekday=dict(jeomchon=weekday(J), shingi=weekday(S)),
    acf=dict(jeomchon=acurve(J), shingi=acurve(S)),
    stats=dict(jeomchon=stat(J), shingi=stat(S)),
    daynight=dict(jeomchon=daynight(J), shingi=daynight(S)),
)
with open(os.path.join(here, "payload.json"), "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False)

print(json.dumps(payload["stats"], ensure_ascii=False))
print("hourly J", payload["hourly"]["jeomchon"])
print("hourly S", payload["hourly"]["shingi"])
print("wd J", payload["weekday"]["jeomchon"])
print("wd S", payload["weekday"]["shingi"])
print("acf24 J", [a for a in payload["acf"]["jeomchon"] if a[0] == 24])
print("acf24 S", [a for a in payload["acf"]["shingi"] if a[0] == 24])
print("points", len(payload["ts"]["jeomchon"]), len(payload["ts"]["shingi"]))

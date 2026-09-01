"""측정 주기별 일주기 곡선 복원력 — 조화회귀(harmonic regression) 방식.

앞선 계산은 측정 시각을 15분 격자에 접었는데, 실제 타임스탬프가 :00/:15에
정렬돼 있지 않고 날짜마다 분이 밀려 빈(bin)이 깨졌다. 여기서는 격자에 의존하지 않고
각 표본의 '하루 중 시각'을 그대로 써서

    v(t) = a0 + Σ_{k=1..K} [ ak·cos(2πkt/24) + bk·sin(2πkt/24) ]

를 최소제곱으로 적합한다. 표본이 몇 시 몇 분에 찍혔든 상관없다.
"""
import json, os, sys, math, urllib.request, datetime as dt
sys.stdout.reconfigure(encoding="utf-8")
root = r"D:\antigravity\db_upload_and_dashboard"
cfg = json.load(open(os.path.join(root, "uploader_config.json"), encoding="utf-8"))
B, key = cfg["supabase_url"].rstrip("/"), cfg["supabase_key"]
H = {"apikey": key, "Authorization": f"Bearer {key}"}
K = 2  # 조화 차수 (사각파를 담으려면 4차는 필요)


def fetch(site, ch):
    rows, off = [], 0
    while True:
        h = dict(H); h["Range"] = f"{off}-{off+999}"
        r = urllib.request.Request(
            B + f"/measure_logs_v2?Site_ID=eq.{site}&Channel_Name=eq.{ch}"
            "&select=Date_Time,TOC_Conc&order=Date_Time.asc", headers=h)
        bb = json.load(urllib.request.urlopen(r, timeout=90)); rows += bb
        if len(bb) < 1000: break
        off += 1000
    return sorted((dt.datetime.fromisoformat(x["Date_Time"]), x["TOC_Conc"]) for x in rows
                  if "2026-08-05" <= x["Date_Time"] < "2026-08-13")


def design(h):
    row = [1.0]
    for k in range(1, K + 1):
        row += [math.cos(2 * math.pi * k * h / 24), math.sin(2 * math.pi * k * h / 24)]
    return row


def solve(A, y):
    """정규방정식 A'A x = A'y 를 가우스 소거로 푼다"""
    m = len(A[0])
    M = [[sum(A[r][i] * A[r][j] for r in range(len(A))) for j in range(m)]
         + [sum(A[r][i] * y[r] for r in range(len(A)))] for i in range(m)]
    for i in range(m):
        p = max(range(i, m), key=lambda r: abs(M[r][i]))
        M[i], M[p] = M[p], M[i]
        if abs(M[i][i]) < 1e-12: return None
        for r in range(m):
            if r == i: continue
            f = M[r][i] / M[i][i]
            for c in range(i, m + 1):
                M[r][c] -= f * M[i][c]
    return [M[i][m] / M[i][i] for i in range(m)]


def fit(series):
    hs = [t.hour + t.minute / 60 + t.second / 3600 for t, _ in series]
    A = [design(h) for h in hs]
    y = [v for _, v in series]
    c = solve(A, y)
    if c is None: return None
    return [sum(ci * di for ci, di in zip(c, design(i / 96 * 24))) for i in range(96)]


def at(curve, want):
    f = max if want == "max" else min
    return curve.index(f(curve)) / 96 * 24


def circ(a, b):
    d = abs(a - b)
    return min(d, 24 - d)


INTERVALS = [(1, "15분"), (2, "30분"), (3, "45분"), (4, "1시간"),
             (6, "1.5시간"), (8, "2시간"), (12, "3시간")]

for label, site, ch in [("점촌 원수 (사인파형)", "jeomchon", "%EC%9B%90%EC%88%98"),
                        ("신기 유입수 (사각파형)", "Shingi", "%EC%9C%A0%EC%9E%85%EC%88%98")]:
    d = fetch(site, ch)
    T = fit(d)
    t_amp = max(T) - min(T); t_min, t_max = at(T, "min"), at(T, "max")
    t_mean = sum(T) / 96
    print("=" * 88)
    print(f"{label}   표본 {len(d)}건")
    print(f"  진실값(15분 적합): 평균 {t_mean:.0f} · 진폭 {t_amp:.0f} · "
          f"최저 {t_min:.1f}시({min(T):.0f}) · 최고 {t_max:.1f}시({max(T):.0f})")
    print()
    print(f"{'주기':<9}{'하루':>5}{'8일표본':>8}{'곡선오차':>9}{'진폭오차':>9}"
          f"{'최저시각':>10}{'최고시각':>10}{'위상흔들림':>11}")
    print("-" * 88)
    for k, name in INTERVALS:
        rm, ae, mn, mx, amps = [], [], [], [], []
        cnt = 0
        for phase in range(k):
            ds = [x for i, x in enumerate(d) if i % k == phase]
            cnt = len(ds)
            c = fit(ds)
            if c is None: continue
            rm.append(math.sqrt(sum((a - b) ** 2 for a, b in zip(c, T)) / 96) / t_amp * 100)
            amps.append(max(c) - min(c))
            ae.append(abs((max(c) - min(c)) - t_amp) / t_amp * 100)
            mn.append(circ(at(c, "min"), t_min)); mx.append(circ(at(c, "max"), t_max))
        spread = (max(amps) - min(amps)) / t_amp * 100 if len(amps) > 1 else 0.0
        print(f"{name:<9}{1440//(k*15):>5}{cnt:>8}{max(rm):>8.0f}%{max(ae):>8.0f}%"
              f"{max(mn):>9.1f}h{max(mx):>9.1f}h{spread:>10.0f}%")
    print()
    print("  모든 값은 시작 위상 중 '최악'. 위상흔들림 = 시작 시각만 바뀌었을 때 진폭이 흔들리는 폭")
    print()

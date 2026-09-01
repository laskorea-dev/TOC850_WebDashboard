import json, os, sys, math, statistics, urllib.request, datetime as dt
sys.stdout.reconfigure(encoding="utf-8")
here = os.path.dirname(os.path.abspath(__file__))
root = r"D:\antigravity\db_upload_and_dashboard"
cfg = json.load(open(os.path.join(root, "uploader_config.json"), encoding="utf-8"))
base, key = cfg["supabase_url"].rstrip("/"), cfg["supabase_key"]
H = {"apikey": key, "Authorization": f"Bearer {key}"}
WD = "월화수목금토일"

rows, off = [], 0
while True:
    h = dict(H); h["Range"] = f"{off}-{off+999}"
    r = urllib.request.Request(
        base + "/measure_logs_v2?Site_ID=eq.jeomchon&select=Date_Time,TOC_Conc,DilutionFactor"
        "&order=Date_Time.asc", headers=h)
    b = json.load(urllib.request.urlopen(r, timeout=90))
    rows += b
    if len(b) < 1000: break
    off += 1000

data = [(dt.datetime.fromisoformat(x["Date_Time"]), x["TOC_Conc"], x["DilutionFactor"]) for x in rows]
data = [x for x in data if x[0] >= dt.datetime(2026, 8, 5)]
data.sort()
print(f"점촌 8월 구간 {len(data)}건  {data[0][0]} ~ {data[-1][0]}  희석 {sorted({x[2] for x in data})}")

vals = [v for _, v, _ in data]
base_med = statistics.median(vals)
mad = statistics.median([abs(v - base_med) for v in vals])
sigma = 1.4826 * mad
print(f"기저 중앙값 {base_med:.1f} · 로버스트 σ {sigma:.1f} (MAD 기반)")
for k in (2, 3, 4):
    print(f"   중앙값+{k}σ = {base_med + k*sigma:.1f}")


def events(thresh, min_pts=2):
    """threshold 초과 연속 구간을 사건으로 묶는다 (15분 이내 간격은 같은 사건)"""
    ev, cur = [], []
    for i, (t, v, _) in enumerate(data):
        if v >= thresh:
            if cur and (t - cur[-1][0]).total_seconds() > 3600:
                ev.append(cur); cur = []
            cur.append((t, v, i))
        elif cur and (data[i][0] - cur[-1][0]).total_seconds() > 3600:
            ev.append(cur); cur = []
    if cur: ev.append(cur)
    return [e for e in ev if len(e) >= min_pts]


def describe(ev, thresh):
    out = []
    for e in ev:
        i0, i1 = e[0][2], e[-1][2]
        peak = max(e, key=lambda x: x[1])
        # 상승 시작: 피크 이전으로 거슬러 올라가며 값이 계속 줄어드는 동안
        j = peak[2]
        while j > 0 and data[j - 1][1] < data[j][1]:
            j -= 1
        k = peak[2]
        while k < len(data) - 1 and data[k + 1][1] < data[k][1]:
            k += 1
        rise_h = (peak[0] - data[j][0]).total_seconds() / 3600
        fall_h = (data[k][0] - peak[0]).total_seconds() / 3600
        out.append(dict(
            start=data[j][0], peak_t=peak[0], end=data[k][0],
            peak=peak[1], foot_lo=data[j][1], foot_hi=data[k][1],
            above_h=(e[-1][0] - e[0][0]).total_seconds() / 3600 + 0.25,
            rise_h=rise_h, fall_h=fall_h,
            rise_rate=(peak[1] - data[j][1]) / rise_h if rise_h else 0.0,
            fall_rate=(peak[1] - data[k][1]) / fall_h if fall_h else 0.0,
            n=len(e), monotone_up=all(data[m][1] <= data[m + 1][1] + 3 for m in range(j, peak[2])),
            monotone_dn=all(data[m][1] >= data[m + 1][1] - 3 for m in range(peak[2], k)),
        ))
    return out


for TH in (100, round(base_med + 3 * sigma), round(base_med + 2 * sigma)):
    ev = events(TH)
    print("\n" + "=" * 76)
    print(f"임계 {TH} mg/L 초과 사건: {len(ev)}건")
    d = describe(ev, TH)
    for x in d:
        print(f"  {x['peak_t']:%m-%d(%a) %H:%M} 피크 {x['peak']:6.1f}  "
              f"상승 {x['rise_h']:4.2f}h({x['foot_lo']:5.1f}→) {x['rise_rate']:6.1f}/h  "
              f"하강 {x['fall_h']:4.2f}h(→{x['foot_hi']:5.1f}) {x['fall_rate']:6.1f}/h  "
              f"초과지속 {x['above_h']:4.2f}h  단조 ↑{x['monotone_up']} ↓{x['monotone_dn']}")
    if len(d) >= 2:
        peaks = [x["peak_t"] for x in d]
        gaps = [(b - a).total_seconds() / 3600 for a, b in zip(peaks, peaks[1:])]
        print(f"  피크 간격(h): {[round(g,1) for g in gaps]}")
        print(f"     → 평균 {sum(gaps)/len(gaps):.1f}h, 24h의 배수로 보면 "
              f"{[round(g/24,2) for g in gaps]}")
        hrs = [p.hour + p.minute / 60 for p in peaks]
        a = [h / 24 * 2 * math.pi for h in hrs]
        c = sum(math.cos(t) for t in a) / len(a); s = sum(math.sin(t) for t in a) / len(a)
        R = math.hypot(c, s)
        mh = (math.atan2(s, c) % (2 * math.pi)) / (2 * math.pi) * 24
        print(f"  피크 시각: {[f'{h:.1f}' for h in hrs]} → 평균 {mh:.1f}시, 집중도 R={R:.2f}")
        print(f"  피크 요일: {[WD[p.weekday()] for p in peaks]}")

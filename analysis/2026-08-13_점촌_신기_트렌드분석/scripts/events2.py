import json, os, sys, math, statistics, urllib.request, datetime as dt
sys.stdout.reconfigure(encoding="utf-8")
root = r"D:\antigravity\db_upload_and_dashboard"
cfg = json.load(open(os.path.join(root, "uploader_config.json"), encoding="utf-8"))
base, key = cfg["supabase_url"].rstrip("/"), cfg["supabase_key"]
H = {"apikey": key, "Authorization": f"Bearer {key}"}
WD = "월화수목금토일"

rows, off = [], 0
while True:
    h = dict(H); h["Range"] = f"{off}-{off+999}"
    r = urllib.request.Request(base + "/measure_logs_v2?Site_ID=eq.jeomchon"
                               "&select=Date_Time,TOC_Conc&order=Date_Time.asc", headers=h)
    b = json.load(urllib.request.urlopen(r, timeout=90)); rows += b
    if len(b) < 1000: break
    off += 1000

data = sorted((dt.datetime.fromisoformat(x["Date_Time"]), x["TOC_Conc"]) for x in rows
              if x["Date_Time"] >= "2026-08-05")
vals = [v for _, v in data]
med = statistics.median(vals)
sig = 1.4826 * statistics.median([abs(v - med) for v in vals])

# 시간대별 기저(중앙값) — 일주기를 감안한 기준선
byh = {}
for t, v in data:
    byh.setdefault(t.hour, []).append(v)
hbase = {h: statistics.median(v) for h, v in byh.items()}

print(f"n={len(data)} · 전체 중앙값 {med:.1f} · 로버스트 σ {sig:.1f}")
print("시간대별 기저(중앙값):", " ".join(f"{h:02d}:{hbase[h]:.0f}" for h in range(24)))

# 100 초과 표본 전수
over = [(t, v) for t, v in data if v >= 100]
print(f"\n100 mg/L 이상 표본 {len(over)}건 (전체의 {len(over)/len(data)*100:.1f}%)")

# 사건 묶기: 1시간 이상 떨어지면 다른 사건
ev, cur = [], []
for t, v in over:
    if cur and (t - cur[-1][0]).total_seconds() > 3600:
        ev.append(cur); cur = []
    cur.append((t, v))
if cur: ev.append(cur)

idx = {t: i for i, (t, _) in enumerate(data)}
print(f"사건 {len(ev)}건\n")
print(f"{'#':<3}{'피크 시각':<20}{'요일':<5}{'피크':>8}{'상승':>7}{'하강':>7}{'표본수':>7}{'초과질량':>10}")
summ = []
for n, e in enumerate(ev, 1):
    pk = max(e, key=lambda x: x[1])
    i = idx[pk[0]]
    j = i
    while j > 0 and data[j - 1][1] < data[j][1]: j -= 1
    k = i
    while k < len(data) - 1 and data[k + 1][1] < data[k][1]: k += 1
    rise = (pk[0] - data[j][0]).total_seconds() / 3600
    fall = (data[k][0] - pk[0]).total_seconds() / 3600
    # 초과질량: 시간대 기저 위로 쌓인 면적 (mg/L·h)
    area = 0.0
    for m in range(j, k):
        dtm = (data[m + 1][0] - data[m][0]).total_seconds() / 3600
        exc = max(0, (data[m][1] + data[m + 1][1]) / 2 - hbase[data[m][0].hour])
        area += exc * dtm
    summ.append(dict(peak_t=pk[0], peak=pk[1], rise=rise, fall=fall, n=len(e), area=area,
                     j=j, k=k, foot=data[j][1]))
    print(f"{n:<3}{pk[0]:%Y-%m-%d %H:%M}   {WD[pk[0].weekday()]:<5}{pk[1]:>8.1f}"
          f"{rise:>6.2f}h{fall:>6.2f}h{len(e):>7}{area:>9.0f}")

print("\n[모양] 각 사건의 원자료 (기저 대비)")
for n, s in enumerate(summ, 1):
    seq = [(data[m][0], data[m][1]) for m in range(max(0, s["j"] - 2), min(len(data), s["k"] + 3))]
    print(f"  #{n} {s['peak_t']:%m-%d}: " + "  ".join(f"{t:%H:%M}={v:.0f}" for t, v in seq))

peaks = [s["peak_t"] for s in summ]
gaps = [(b - a).total_seconds() / 3600 for a, b in zip(peaks, peaks[1:])]
print(f"\n[간격] {[round(g,1) for g in gaps]} 시간  = {[round(g/24,2) for g in gaps]} 일")
hrs = [p.hour + p.minute / 60 for p in peaks]
a = [h / 24 * 2 * math.pi for h in hrs]
c = sum(math.cos(t) for t in a) / len(a); s_ = sum(math.sin(t) for t in a) / len(a)
R = math.hypot(c, s_); mh = (math.atan2(s_, c) % (2 * math.pi)) / (2 * math.pi) * 24
print(f"[시각] {[f'{h:.2f}' for h in hrs]} → 평균 {mh:.2f}시 · 집중도 R={R:.2f}")
lo, hi = min(hrs), max(hrs)
win = hi - lo
frac = sum(1 for t, _ in data if lo <= t.hour + t.minute / 60 <= hi) / len(data)
print(f"[검정] 모든 피크가 {lo:.2f}~{hi:.2f}시({win:.1f}시간 폭) 안에 들어옴. "
      f"이 시간대의 표본 비중 {frac*100:.0f}% → 우연일 확률 ≈ {frac**len(peaks)*100:.2f}%")
print(f"[요일] {[WD[p.weekday()] for p in peaks]}")
print(f"[날짜] {[f'{p:%m-%d}' for p in peaks]}  (관측 8/5~8/13 중 {len({p.date() for p in peaks})}일에 발생)")

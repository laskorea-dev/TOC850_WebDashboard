"""측정 간격 15/30/60분에서 '급격한 상승'을 얼마나 복원할 수 있는지 실측."""
import json, os, sys, statistics, urllib.request, datetime as dt
sys.stdout.reconfigure(encoding="utf-8")
root = r"D:\antigravity\db_upload_and_dashboard"
cfg = json.load(open(os.path.join(root, "uploader_config.json"), encoding="utf-8"))
base, key = cfg["supabase_url"].rstrip("/"), cfg["supabase_key"]
H = {"apikey": key, "Authorization": f"Bearer {key}"}

rows, off = [], 0
while True:
    h = dict(H); h["Range"] = f"{off}-{off+999}"
    r = urllib.request.Request(base + "/measure_logs_v2?Site_ID=eq.jeomchon"
                               "&select=Date_Time,TOC_Conc&order=Date_Time.asc", headers=h)
    b = json.load(urllib.request.urlopen(r, timeout=90)); rows += b
    if len(b) < 1000: break
    off += 1000

data = sorted((dt.datetime.fromisoformat(x["Date_Time"]), x["TOC_Conc"]) for x in rows
              if "2026-08-05" <= x["Date_Time"] < "2026-08-13")
TH = 100

# --- 원자료 기준 진실값 --------------------------------------------------
def rising_limb(series, peak_t):
    """피크 직전, 값이 계속 오르는 구간"""
    i = min(range(len(series)), key=lambda m: abs((series[m][0] - peak_t).total_seconds()))
    j = i
    while j > 0 and series[j - 1][1] < series[j][1]:
        j -= 1
    return series[j:i + 1]

TRUTH = []
for ts in ["2026-08-05 14:12", "2026-08-10 14:30"]:
    pt = dt.datetime.fromisoformat(ts)
    limb = rising_limb(data, pt)
    dur = (limb[-1][0] - limb[0][0]).total_seconds() / 3600
    rate = (limb[-1][1] - limb[0][1]) / dur
    TRUTH.append(dict(t=pt, n=len(limb), dur=dur, rate=rate, peak=limb[-1][1], foot=limb[0][1]))
    print(f"[진실값 15분] {pt:%m-%d %H:%M}  상승 {dur:.2f}h · {len(limb)}점 · "
          f"{limb[0][1]:.1f}→{limb[-1][1]:.1f} · {rate:.1f} mg/L·h")

print()
print(f"{'간격':<8}{'위상':<8}{'검출(2점)':>10}{'헌팅오검출':>11}   상승 복원 (점수 / 추정속도 / 오차)")
print("-" * 100)

def detect(series, rule="2pt"):
    ev, cur = [], []
    for t, v in series:
        if v >= TH:
            if cur and (t - cur[-1][0]).total_seconds() > 2.5 * 3600:
                ev.append(cur); cur = []
            cur.append((t, v))
        elif cur and (t - cur[-1][0]).total_seconds() > 2.5 * 3600:
            ev.append(cur); cur = []
    if cur: ev.append(cur)
    return [e for e in ev if (len(e) >= 2 if rule == "2pt" else True)]

SPIKES = [dt.datetime(2026, 8, 5, 10, 57), dt.datetime(2026, 8, 7, 16, 30)]

for step, name in [(1, "15분"), (2, "30분"), (4, "60분")]:
    for phase in range(step):
        ds = [x for i, x in enumerate(data) if i % step == phase]
        ev = detect(ds)
        peaks = [max(e, key=lambda x: x[1])[0] for e in ev]
        hit = sum(1 for tr in TRUTH if any(abs((p - tr["t"]).total_seconds()) < 3 * 3600 for p in peaks))
        false = sum(1 for p in peaks if any(abs((p - s).total_seconds()) < 1800 for s in SPIKES))
        parts = []
        for tr in TRUTH:
            limb = rising_limb(ds, tr["t"])
            if len(limb) >= 2:
                d = (limb[-1][0] - limb[0][0]).total_seconds() / 3600
                rt = (limb[-1][1] - limb[0][1]) / d if d else 0
                err = (rt - tr["rate"]) / tr["rate"] * 100
                parts.append(f"{len(limb)}점 {rt:5.1f} ({err:+5.0f}%)")
            else:
                parts.append(f"{len(limb)}점  복원불가    ")
        print(f"{name:<8}+{phase*15:<7}{hit}/2{'':>7}{false:>6}      " + " | ".join(parts))

print()
print("── '상승을 본다'의 기준: 상승 구간에 표본이 3점 이상 남는가 ──")
for tr in TRUTH:
    print(f"  {tr['t']:%m-%d %H:%M} 상승 {tr['dur']:.2f}h  →  "
          f"15분 {int(tr['dur']*4)+1}점 · 30분 {int(tr['dur']*2)+1}점 · 60분 {int(tr['dur'])+1}점")
fastest = min(t["dur"] for t in TRUTH)
print(f"\n  관측된 가장 빠른 상승 {fastest:.2f}시간 → 3점을 확보하려면 간격 ≤ {fastest/2*60:.0f}분")

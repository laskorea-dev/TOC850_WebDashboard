"""15분 자료를 60분으로 솎아 내려, 사건 검출력이 얼마나 남는지 실측한다."""
import json, os, sys, math, statistics, urllib.request, datetime as dt
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

# 15분 간격이 유지된 구간만 사용 (8/13 이전)
data = sorted((dt.datetime.fromisoformat(x["Date_Time"]), x["TOC_Conc"]) for x in rows
              if "2026-08-05" <= x["Date_Time"] < "2026-08-13")
print(f"원자료(15분) {len(data)}건  {data[0][0]:%m-%d %H:%M} ~ {data[-1][0]:%m-%d %H:%M}")

TRUE_EVENTS = ["08-05 14:12", "08-10 14:30"]   # 이 구간에 든 추세형
TRUE_SPIKES = ["08-05 10:57", "08-07 16:30"]
print(f"기준: 추세형 {TRUE_EVENTS} · 단일표본형 {TRUE_SPIKES}\n")

TH = 100


def detect(series, rule):
    """rule='any' 1점만 넘어도 사건, rule='2pt' 연속 2점 이상"""
    ev, cur = [], []
    for i, (t, v) in enumerate(series):
        if v >= TH:
            if cur and (t - cur[-1][0]).total_seconds() > 2.5 * 3600:
                ev.append(cur); cur = []
            cur.append((t, v))
        elif cur and (t - cur[-1][0]).total_seconds() > 2.5 * 3600:
            ev.append(cur); cur = []
    if cur: ev.append(cur)
    return [e for e in ev if (len(e) >= 2 if rule == "2pt" else True)]


print("── 60분으로 솎았을 때 (시작 위상 4가지 전부 시험) ──")
print(f"{'위상':<8}{'표본':>6}{'1점규칙 검출':>14}{'2점규칙 검출':>14}   내역")
for phase in range(4):
    ds = [x for i, x in enumerate(data) if i % 4 == phase]
    a = detect(ds, "any")
    b = detect(ds, "2pt")
    lab = lambda ev: [f"{max(e,key=lambda x:x[1])[0]:%m-%d %H:%M}" for e in ev]
    print(f"  +{phase*15:>2}분{len(ds):>6}{len(a):>14}{len(b):>14}   1점:{lab(a)}  2점:{lab(b)}")

print("\n── 원자료(15분) 대조 ──")
a = detect(data, "any"); b = detect(data, "2pt")
lab = lambda ev: [f"{max(e,key=lambda x:x[1])[0]:%m-%d %H:%M}" for e in ev]
print(f"  15분 {len(data)}표본 · 1점규칙 {len(a)}건 {lab(a)} · 2점규칙 {len(b)}건 {lab(b)}")

print("\n── 일주기 검출력은 유지되는가 ──")


def hourly_profile(series):
    byh = {}
    for t, v in series:
        byh.setdefault(t.hour, []).append(v)
    return {h: sum(v) / len(v) for h, v in sorted(byh.items())}


def movavg(x, w):
    n, half = len(x), w // 2
    return [sum(x[max(0, i-half):min(n, i+half+1)]) / (min(n, i+half+1) - max(0, i-half)) for i in range(n)]


def acf24(series, per_day):
    v = [x[1] for x in series]
    tr = movavg(v, per_day)
    d = [a - b for a, b in zip(v, tr)]
    n = len(d); m = sum(d) / n
    den = sum((a - m) ** 2 for a in d)
    lag = per_day
    return sum((d[i] - m) * (d[i + lag] - m) for i in range(n - lag)) / den


p15 = hourly_profile(data)
print(f"  15분: 추세제거 24h 자기상관 {acf24(data, 96):+.3f} · "
      f"최저 {min(p15, key=p15.get):02d}시 최고 {max(p15, key=p15.get):02d}시 "
      f"진폭 {max(p15.values())-min(p15.values()):.1f}")
for phase in range(4):
    ds = [x for i, x in enumerate(data) if i % 4 == phase]
    p = hourly_profile(ds)
    print(f"  60분(+{phase*15:>2}분): 추세제거 24h 자기상관 {acf24(ds, 24):+.3f} · "
          f"최저 {min(p, key=p.get):02d}시 최고 {max(p, key=p.get):02d}시 "
          f"진폭 {max(p.values())-min(p.values()):.1f}")

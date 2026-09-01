"""측정 주기별로 '일주기 곡선'을 얼마나 정확히 복원하는지 실측한다.

기준(진실값): 15분 자료를 시각별로 접은 평균 곡선(하루 96점).
시험: 주기 I분으로 솎아 낸 자료를 같은 방식으로 접고, 선형보간으로 96점에 되돌린 뒤
      진실값과 비교한다. 시작 위상(어느 분에 첫 측정을 하느냐)을 전부 돌린다.
"""
import json, os, sys, math, statistics, urllib.request, datetime as dt
sys.stdout.reconfigure(encoding="utf-8")
root = r"D:\antigravity\db_upload_and_dashboard"
cfg = json.load(open(os.path.join(root, "uploader_config.json"), encoding="utf-8"))
b_, key = cfg["supabase_url"].rstrip("/"), cfg["supabase_key"]
H = {"apikey": key, "Authorization": f"Bearer {key}"}


def fetch(site, ch):
    rows, off = [], 0
    while True:
        h = dict(H); h["Range"] = f"{off}-{off+999}"
        r = urllib.request.Request(
            b_ + f"/measure_logs_v2?Site_ID=eq.{site}&Channel_Name=eq.{ch}"
            "&select=Date_Time,TOC_Conc&order=Date_Time.asc", headers=h)
        bb = json.load(urllib.request.urlopen(r, timeout=90)); rows += bb
        if len(bb) < 1000: break
        off += 1000
    return sorted((dt.datetime.fromisoformat(x["Date_Time"]), x["TOC_Conc"]) for x in rows
                  if "2026-08-05" <= x["Date_Time"] < "2026-08-13")


def fold(series, slots=96):
    """시각(하루 96슬롯)별 평균"""
    bins = [[] for _ in range(slots)]
    for t, v in series:
        s = (t.hour * 60 + t.minute) * slots // 1440
        bins[s].append(v)
    return [sum(b) / len(b) if b else None for b in bins]


def interp_circular(vals):
    """None을 원형 선형보간으로 채운다"""
    n = len(vals)
    known = [i for i, v in enumerate(vals) if v is not None]
    if not known: return vals
    out = list(vals)
    for i in range(n):
        if out[i] is not None: continue
        lo = max((k for k in known if k <= i), default=None)
        hi = min((k for k in known if k >= i), default=None)
        if lo is None: lo = known[-1] - n
        if hi is None: hi = known[0] + n
        a, b = vals[lo % n], vals[hi % n]
        out[i] = a + (b - a) * (i - lo) / (hi - lo) if hi != lo else a
    return out


def peak_slot(p, want="max"):
    f = max if want == "max" else min
    i = p.index(f(p))
    return i / 96 * 24


INTERVALS = [(1, "15분"), (2, "30분"), (3, "45분"), (4, "1시간"),
             (6, "1.5시간"), (8, "2시간"), (12, "3시간")]

for label, site, ch in [("점촌 원수 (사인파형)", "jeomchon", "%EC%9B%90%EC%88%98"),
                        ("신기 유입수 (사각파형)", "Shingi", "%EC%9C%A0%EC%9E%85%EC%88%98")]:
    d = fetch(site, ch)
    truth = interp_circular(fold(d))
    t_amp = max(truth) - min(truth)
    t_min, t_max = peak_slot(truth, "min"), peak_slot(truth, "max")
    t_mean = sum(truth) / len(truth)
    print("=" * 92)
    print(f"{label}   n={len(d)}   진실값: 평균 {t_mean:.0f} · 진폭 {t_amp:.0f} · "
          f"최저 {t_min:.1f}시 · 최고 {t_max:.1f}시")
    print(f"{'주기':<9}{'하루':>5}{'곡선오차':>9}{'진폭오차':>10}{'최저시각':>11}{'최고시각':>11}"
          f"{'일평균':>9}   {'위상별 진폭 산포'}")
    print("-" * 92)
    for k, name in INTERVALS:
        rmses, amps, mins, maxs, means = [], [], [], [], []
        for phase in range(k):
            ds = [x for i, x in enumerate(d) if i % k == phase]
            p = interp_circular(fold(ds))
            if any(v is None for v in p): continue
            rmses.append(math.sqrt(sum((a - b) ** 2 for a, b in zip(p, truth)) / 96))
            amps.append(max(p) - min(p))
            mins.append(peak_slot(p, "min")); maxs.append(peak_slot(p, "max"))
            means.append(sum(p) / len(p))

        def circ_err(vals, ref):
            e = []
            for v in vals:
                x = abs(v - ref)
                e.append(min(x, 24 - x))
            return max(e)

        amp_err = max(abs(a - t_amp) / t_amp * 100 for a in amps)
        mean_err = max(abs(m - t_mean) / t_mean * 100 for m in means)
        spread = (max(amps) - min(amps)) / t_amp * 100 if len(amps) > 1 else 0.0
        print(f"{name:<9}{1440//(k*15):>5}{max(rmses)/t_amp*100:>8.0f}%{amp_err:>9.0f}%"
              f"{circ_err(mins, t_min):>9.1f}h{circ_err(maxs, t_max):>10.1f}h"
              f"{mean_err:>8.1f}%   {spread:>5.0f}%")
    print()
    print("  곡선오차 = 복원 곡선과 진실 곡선의 RMSE (진폭 대비 %) · 값은 위상 중 최악")
    print("  위상별 진폭 산포 = 시작 시각만 다를 뿐인데 진폭이 얼마나 흔들리는가 (작을수록 신뢰)")
    print()

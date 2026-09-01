"""'신기에는 점촌 같은 고주파 변동이 없다'를 검정한다.

국소 이동중앙값(±3점)에서 얼마나 벗어나는지를 보고, 한 점만 튀었다가
바로 복귀하는 성분의 크기를 두 지점에서 비교한다.
"""
import json, os, sys, statistics, urllib.request, datetime as dt
sys.stdout.reconfigure(encoding="utf-8")
root = r"D:\antigravity\db_upload_and_dashboard"
cfg = json.load(open(os.path.join(root, "uploader_config.json"), encoding="utf-8"))
base, key = cfg["supabase_url"].rstrip("/"), cfg["supabase_key"]
H = {"apikey": key, "Authorization": f"Bearer {key}"}


def fetch(site, ch):
    rows, off = [], 0
    while True:
        h = dict(H); h["Range"] = f"{off}-{off+999}"
        r = urllib.request.Request(
            base + f"/measure_logs_v2?Site_ID=eq.{site}&Channel_Name=eq.{ch}"
            "&select=Date_Time,TOC_Conc&order=Date_Time.asc", headers=h)
        b = json.load(urllib.request.urlopen(r, timeout=90)); rows += b
        if len(b) < 1000: break
        off += 1000
    return sorted((dt.datetime.fromisoformat(x["Date_Time"]), x["TOC_Conc"]) for x in rows
                  if "2026-08-05" <= x["Date_Time"] < "2026-08-13")


for label, site, ch in [("점촌 원수", "jeomchon", "%EC%9B%90%EC%88%98"),
                        ("신기 유입수", "Shingi", "%EC%9C%A0%EC%9E%85%EC%88%98")]:
    d = fetch(site, ch)
    v = [x[1] for x in d]
    n = len(v)
    print("=" * 74)
    print(f"{label}  n={n}  평균 {sum(v)/n:.1f}")

    # 국소 이동중앙값 대비 잔차
    res = []
    for i in range(n):
        w = v[max(0, i - 3):min(n, i + 4)]
        med = statistics.median(w)
        res.append((d[i][0], v[i], v[i] - med, (v[i] - med) / med * 100 if med else 0))

    ar = [abs(r[2]) for r in res]
    rel = [abs(r[3]) for r in res]
    print(f"  국소중앙값 대비 잔차: 중앙 {statistics.median(ar):.1f} · "
          f"p95 {sorted(ar)[int(n*0.95)]:.1f} · 최대 {max(ar):.1f} (절대, mg/L)")
    print(f"                       중앙 {statistics.median(rel):.1f}% · "
          f"p95 {sorted(rel)[int(n*0.95)]:.1f}% · 최대 {max(rel):.0f}% (상대)")

    # 단일표본 튐: 자기는 크게 벗어나는데 앞뒤는 서로 가까운 경우
    spikes = []
    for i in range(1, n - 1):
        prev, cur, nxt = v[i - 1], v[i], v[i + 1]
        neigh = (prev + nxt) / 2
        if neigh <= 0: continue
        jump = abs(cur - neigh) / neigh * 100
        cont = abs(nxt - prev) / neigh * 100          # 앞뒤끼리는 얼마나 이어지나
        if jump >= 50 and cont <= 25:
            spikes.append((d[i][0], prev, cur, nxt, jump))
    print(f"  단일표본 튐(이웃평균 대비 50%↑ 이탈 & 앞뒤는 25% 이내): {len(spikes)}건")
    for t, a, b_, c, j in spikes[:10]:
        print(f"     {t:%m-%d %H:%M}  {a:.1f} → [{b_:.1f}] → {c:.1f}   ({j:+.0f}%)")

    # 표본 간 변화율 분포
    diffs = [abs(v[i + 1] - v[i]) for i in range(n - 1)]
    reld = [abs(v[i + 1] - v[i]) / v[i] * 100 for i in range(n - 1) if v[i] > 0]
    print(f"  이웃 표본 간 변화: 중앙 {statistics.median(diffs):.1f} mg/L "
          f"({statistics.median(reld):.1f}%) · p99 {sorted(diffs)[int(len(diffs)*0.99)]:.1f} mg/L "
          f"({sorted(reld)[int(len(reld)*0.99)]:.0f}%)")

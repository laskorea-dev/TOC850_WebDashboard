import json, os, sys, statistics, urllib.request, datetime as dt
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
    r = urllib.request.Request(base + "/measure_logs_v2?Site_ID=eq.jeomchon"
                               "&select=Date_Time,TOC_Conc&order=Date_Time.asc", headers=h)
    b = json.load(urllib.request.urlopen(r, timeout=90)); rows += b
    if len(b) < 1000: break
    off += 1000

data = sorted((dt.datetime.fromisoformat(x["Date_Time"]), x["TOC_Conc"]) for x in rows
              if x["Date_Time"] >= "2026-08-05")

# 3개 실사건 + 2개 단일표본 스파이크
EVENTS = [
    ("2026-08-05 14:12", "trend"),
    ("2026-08-10 14:30", "trend"),
    ("2026-08-13 13:02", "trend"),
    ("2026-08-05 10:57", "spike"),
    ("2026-08-07 16:30", "spike"),
]
idx = {t: i for i, (t, _) in enumerate(data)}
out = []
for ts, kind in EVENTS:
    pt = dt.datetime.fromisoformat(ts)
    i = min(range(len(data)), key=lambda m: abs((data[m][0]-pt).total_seconds()))
    pt = data[i][0]
    lo = max(0, i - 14); hi = min(len(data), i + 22)
    pts = [[round((data[m][0] - pt).total_seconds() / 3600, 3), data[m][1]]
           for m in range(lo, hi)
           if abs((data[m][0] - pt).total_seconds()) <= 6.5 * 3600]
    # 상승/하강 속도
    j = i
    while j > 0 and data[j - 1][1] < data[j][1]: j -= 1
    k = i
    while k < len(data) - 1 and data[k + 1][1] < data[k][1]: k += 1
    rise_h = (data[i][0] - data[j][0]).total_seconds() / 3600
    fall_h = (data[k][0] - data[i][0]).total_seconds() / 3600
    out.append(dict(
        label=f"{pt:%m-%d}({WD[pt.weekday()]}) {pt:%H:%M}",
        date=f"{pt:%m-%d}", wd=WD[pt.weekday()], hour=round(pt.hour + pt.minute / 60, 2),
        kind=kind, peak=data[i][1], foot=data[j][1],
        riseH=round(rise_h, 2), fallH=round(fall_h, 2),
        riseRate=round((data[i][1] - data[j][1]) / rise_h, 1) if rise_h else None,
        fallRate=round((data[i][1] - data[k][1]) / fall_h, 1) if fall_h else None,
        nRise=i - j + 1,
        pts=pts,
    ))
    e = out[-1]
    print(f"{e['label']:<18}{e['kind']:<6} 피크{e['peak']:7.1f} 발치{e['foot']:6.1f} "
          f"상승 {e['riseH']}h({e['nRise']}점) {e['riseRate']}/h  하강 {e['fallH']}h {e['fallRate']}/h")

pl = os.path.join(here, "payload.json")
P = json.load(open(pl, encoding="utf-8"))
P["events"] = out
json.dump(P, open(pl, "w", encoding="utf-8"), ensure_ascii=False)
print("saved")

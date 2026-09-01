import json, os, sys, urllib.request
sys.stdout.reconfigure(encoding="utf-8")

root = r"D:\antigravity\db_upload_and_dashboard"
cfg = json.load(open(os.path.join(root, "uploader_config.json"), encoding="utf-8"))
base = cfg["supabase_url"].rstrip("/")
key = cfg["supabase_key"]
H = {"apikey": key, "Authorization": f"Bearer {key}"}

out = {}
for site in ["jeomchon", "Shingi"]:
    rows, offset = [], 0
    while True:
        h = dict(H)
        h["Range"] = f"{offset}-{offset+999}"
        url = (base + f"/measure_logs_v2?Site_ID=eq.{site}"
               "&select=Date_Time,Channel,Channel_Name,TOC_Conc,DilutionFactor,Device_ID,created_at"
               "&order=Date_Time.asc")
        res = urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=90)
        batch = json.load(res)
        rows += batch
        if len(batch) < 1000:
            break
        offset += 1000
    out[site] = rows
    print(site, len(rows))

here = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(here, "data.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False)
print("saved")

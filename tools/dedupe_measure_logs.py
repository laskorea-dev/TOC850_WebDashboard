"""measure_logs_v2 중복 행 정리 도구 (수동 실행).

## 무엇을 하는가

한 지점(site_id)에서 `(Date_Time, Channel)` 이 같은 행이 둘 이상이면 **가장 작은 id 하나만
남기고 나머지를 삭제**한다. 삭제 대상은 실행 전에 JSON 파일로 통째로 백업한다.

## 왜 생기는가

업로더가 증분 기준점(마지막 업로드 시각)을 잃으면 과거 구간을 통째로 재전송한다.
`measure_logs_v2` 에 `(Site_ID, Date_Time, Channel)` 유일 제약이 없어 그대로 두 번 쌓인다.
근본 해결은 유일 인덱스 + upsert 이지만 스키마 변경이므로(`.agents/AGENTS.md` §2)
그때까지는 이 스크립트로 사후 정리한다.

## 사용법

    python tools/dedupe_measure_logs.py <site_id>            # 조회만 (기본)
    python tools/dedupe_measure_logs.py <site_id> --apply    # 실제 삭제

## 안전장치 — 풀지 말 것

- **값이 다른 중복은 삭제하지 않는다.** TOC_Conc / DilutionFactor 가 하나라도 다르면
  그 그룹은 건너뛰고 목록만 출력한다. 재전송이 아니라 실제로 다른 측정일 수 있다.
- 삭제 대상 전체를 `dedupe_backup_<site>_<n>건.json` 으로 먼저 저장한다.
- `--apply` 없이는 아무것도 지우지 않는다.

## 실행 이력

    2026-08-13  jeomchon  752건 삭제 (2026-07-30 ~ 08-12 재전송분)
                회의록: meeting_notes/2026-08-13_shingi_site_id_merge.md
"""
import json
import os
import sys
import urllib.request
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")

args = [a for a in sys.argv[1:] if not a.startswith("--")]
APPLY = "--apply" in sys.argv
if len(args) != 1:
    print(__doc__)
    sys.exit(2)
SITE = args[0]

here = os.path.dirname(os.path.abspath(__file__))
cfg = json.load(open(os.path.join(here, "..", "uploader_config.json"), encoding="utf-8"))
base = cfg["supabase_url"].rstrip("/")
if not base.endswith("/rest/v1"):
    base += "/rest/v1"
key = cfg["supabase_key"]
H = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def req(path, method="GET", data=None, prefer=None):
    headers = dict(H)
    if prefer:
        headers["Prefer"] = prefer
    r = urllib.request.Request(
        base + path,
        data=json.dumps(data).encode("utf-8") if data is not None else None,
        headers=headers,
        method=method,
    )
    res = urllib.request.urlopen(r, timeout=120)
    body = res.read()
    return res, (json.loads(body.decode("utf-8")) if body else [])


# --- 전체 행 수집 (페이징) --------------------------------------------------
rows, offset = [], 0
while True:
    h = dict(H)
    h["Range"] = f"{offset}-{offset+999}"
    r = urllib.request.Request(
        base + f"/measure_logs_v2?Site_ID=eq.{SITE}"
        "&select=id,Date_Time,Channel,TOC_Conc,DilutionFactor,Device_ID,created_at"
        "&order=id.asc",
        headers=h,
    )
    batch = json.load(urllib.request.urlopen(r, timeout=120))
    rows += batch
    if len(batch) < 1000:
        break
    offset += 1000

print(f"지점 '{SITE}' · 전체 {len(rows)}건")

groups = defaultdict(list)
for r in rows:
    groups[(r["Date_Time"], r["Channel"])].append(r)
dups = {k: v for k, v in groups.items() if len(v) > 1}
print(f"고유 (시각, 채널): {len(groups)}개 · 중복 그룹: {len(dups)}개")

if not dups:
    print("중복이 없습니다. 종료합니다.")
    sys.exit(0)

doomed, conflicted = [], []
for k, v in sorted(dups.items()):
    vals = {(x["TOC_Conc"], x["DilutionFactor"]) for x in v}
    if len(vals) > 1:
        conflicted.append((k, v))
        continue
    keep = min(v, key=lambda x: x["id"])
    doomed += [x for x in v if x["id"] != keep["id"]]

if conflicted:
    print(f"\n[건너뜀] 값이 서로 다른 중복 그룹 {len(conflicted)}개 — 수동 확인 필요:")
    for k, v in conflicted[:10]:
        print(f"   {k}: {[(x['id'], x['TOC_Conc'], x['DilutionFactor']) for x in v]}")

print(f"\n삭제 대상: {len(doomed)}건")
if doomed:
    ts = sorted(x["Date_Time"] for x in doomed)
    print(f"   구간 {ts[0]} ~ {ts[-1]}")
    ca = sorted({x["created_at"][:19] for x in doomed})
    print(f"   적재 시각(created_at) 종류 {len(ca)}개: {ca[:5]}{' …' if len(ca) > 5 else ''}")

if not APPLY:
    print("\n조회만 했습니다. 실제로 지우려면 --apply 를 붙이십시오.")
    sys.exit(0)

backup = os.path.join(here, f"dedupe_backup_{SITE}_{len(doomed)}건.json")
with open(backup, "w", encoding="utf-8") as f:
    json.dump(doomed, f, ensure_ascii=False, indent=1)
print(f"\n백업 저장: {backup}")

ids = [x["id"] for x in doomed]
deleted = 0
for i in range(0, len(ids), 200):
    chunk = ids[i:i + 200]
    res, body = req(
        f"/measure_logs_v2?id=in.({','.join(str(v) for v in chunk)})",
        method="DELETE",
        prefer="return=representation",
    )
    deleted += len(body)
    print(f"   삭제 {deleted}/{len(ids)}")

# --- 사후 확인 -------------------------------------------------------------
r = urllib.request.Request(
    base + f"/measure_logs_v2?Site_ID=eq.{SITE}&select=id&limit=1",
    headers={**H, "Prefer": "count=exact"},
)
res = urllib.request.urlopen(r, timeout=60)
total = res.headers.get("Content-Range").split("/")[1]
print(f"\n완료 · {deleted}건 삭제 · 지점 '{SITE}' 잔여 {total}건 (기대값 {len(rows) - len(doomed)})")

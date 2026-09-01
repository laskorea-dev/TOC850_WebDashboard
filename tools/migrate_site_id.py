"""지점 식별자(site_id) 교정·통합 도구 (수동 실행).

## 무엇을 하는가

한 기기(device_id)에 대해
  1) `device_config.site_id` 를 새 값으로 교정하고
  2) 그 기기의 과거 `measure_logs_v2.Site_ID` 를 새 값으로 통합한다.

## 왜 필요한가

대시보드는 두 값을 다르게 쓴다 (`dashboard/src/App.jsx`).

  - 접속 허가 판정 : `device_config` 를 `site_id` **또는** `site_name` 으로 조회
  - 데이터 조회    : URL 의 `?site=` 값이 아니라 **`device_config.site_id`** 로
                     `measure_logs_v2.Site_ID` 를 필터

따라서 `device_config.site_id` 가 호스트명 등으로 동결되어 있으면
"사이트 이름으로는 접속되는데 데이터가 안 보이는" 증상이 난다.
또 업로더에서 Site ID 를 나중에 바꾸면 그 이전 데이터는 옛 Site_ID 로 남아
같은 지점인데도 화면에서 끊겨 보인다. 이 스크립트는 그 둘을 한 번에 맞춘다.

업로더 v5.4 부터는 `sync_device_config_to_supabase()` 가 매 동기화마다
`device_config` 를 자동 교정하므로 1)은 대개 저절로 풀린다.
**과거 데이터 통합(2)은 자동화되어 있지 않아 이 스크립트가 필요하다.**

## 사용법

    python tools/migrate_site_id.py <device_id> <old_site_id> <new_site_id>

인자를 주지 않으면 아래 기본값(2026-08-13 신기폐수처리장 작업)으로 동작한다.
멱등하므로 두 번 실행해도 안전하다.

## 실행 이력

    2026-08-13  TMSTOC-250701-01  TMSTOC-250701-01 → Shingi   1265건 통합
                (신기폐수처리장. 회의록: meeting_notes/2026-08-13_shingi_site_id_merge.md)

## 안전장치

옛 Site_ID 를 쓰는 **다른** 기기의 데이터가 하나라도 있으면 중단한다.
남의 지점 데이터를 빨아들이는 사고를 막기 위한 것이므로 이 검사를 풀지 말 것.

접속 정보는 저장소 루트의 `uploader_config.json` 에서 읽는다.
"""
import json
import os
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

DEFAULTS = ("TMSTOC-250701-01", "TMSTOC-250701-01", "Shingi")

args = sys.argv[1:]
if args and len(args) != 3:
    print(__doc__)
    sys.exit(2)
DEVICE_ID, OLD_SITE_ID, NEW_SITE_ID = tuple(args) if args else DEFAULTS

here = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(here, "..", "uploader_config.json")
cfg = json.load(open(config_path, encoding="utf-8"))
base = cfg["supabase_url"].rstrip("/")
if not base.endswith("/rest/v1"):
    base += "/rest/v1"
key = cfg["supabase_key"]
H = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def get(path, prefer=None):
    headers = dict(H)
    if prefer:
        headers["Prefer"] = prefer
    res = urllib.request.urlopen(urllib.request.Request(base + path, headers=headers), timeout=60)
    return json.load(res), res.headers.get("Content-Range")


def count(path):
    _, rng = get(path + "&select=id&limit=1", prefer="count=exact")
    return int(rng.split("/")[1])


def patch(path, payload):
    req = urllib.request.Request(
        base + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={**H, "Prefer": "return=representation"},
        method="PATCH",
    )
    res = urllib.request.urlopen(req, timeout=180)
    return res.status, json.load(res)


print(f"대상: device_id={DEVICE_ID} · Site_ID '{OLD_SITE_ID}' → '{NEW_SITE_ID}'\n")

conf, _ = get(f"/device_config?device_id=eq.{DEVICE_ID}&select=device_id,site_id,site_name")
print(f"[변경 전] device_config : {conf}")
if not conf:
    print(f"[중단] device_config 에 '{DEVICE_ID}' 행이 없습니다. 업로더에서 설정 저장을 1회 실행하십시오.")
    sys.exit(1)

n_old = count(f"/measure_logs_v2?Device_ID=eq.{DEVICE_ID}&Site_ID=eq.{OLD_SITE_ID}")
n_new = count(f"/measure_logs_v2?Device_ID=eq.{DEVICE_ID}&Site_ID=eq.{NEW_SITE_ID}")
n_foreign = count(f"/measure_logs_v2?Site_ID=eq.{OLD_SITE_ID}&Device_ID=neq.{DEVICE_ID}")
print(f"[변경 전] 측정 데이터   : {OLD_SITE_ID}={n_old}건, {NEW_SITE_ID}={n_new}건")

if n_foreign:
    print(f"[중단] Site_ID='{OLD_SITE_ID}' 인데 다른 기기의 데이터가 {n_foreign}건 있습니다. 수동 확인 필요.")
    sys.exit(1)

status, rows = patch(f"/device_config?device_id=eq.{DEVICE_ID}", {"site_id": NEW_SITE_ID})
print(f"[1/2] device_config  HTTP {status} · {len(rows)}건 갱신")

if n_old:
    status, rows = patch(
        f"/measure_logs_v2?Device_ID=eq.{DEVICE_ID}&Site_ID=eq.{OLD_SITE_ID}",
        {"Site_ID": NEW_SITE_ID},
    )
    print(f"[2/2] measure_logs_v2  HTTP {status} · {len(rows)}건 갱신")
else:
    print("[2/2] 이미 통합되어 있습니다. 건너뜁니다.")

conf, _ = get(f"/device_config?device_id=eq.{DEVICE_ID}&select=device_id,site_id,site_name")
print(f"[변경 후] device_config : {conf}")
print(
    f"[변경 후] 측정 데이터   : {OLD_SITE_ID}="
    f"{count(f'/measure_logs_v2?Device_ID=eq.{DEVICE_ID}&Site_ID=eq.{OLD_SITE_ID}')}건, "
    f"{NEW_SITE_ID}={count(f'/measure_logs_v2?Device_ID=eq.{DEVICE_ID}&Site_ID=eq.{NEW_SITE_ID}')}건"
)

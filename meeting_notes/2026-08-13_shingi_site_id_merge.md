# 2026-08-13 · 신기폐수처리장 지점 식별자 통합 및 과거 데이터 병합

**참석**: 개발실
**배경**: 신기폐수처리장(계측기 `TMSTOC-250701-01`)에 업로더를 반입하고 지점 식별자를 `Shingi`로
설정하였으나, 대시보드에서 최신 데이터가 보이지 않고 접속도 site_id가 아닌 **사이트 이름**으로만
가능하다는 현장 보고가 접수되었다.

---

## 1. 원인 — 7월 평택(점촌) 건과 동일 계열

Supabase 실데이터를 직접 조회하여 확증하였다.

| 항목 | 값 |
|---|---|
| `device_config.site_id` | `TMSTOC-250701-01` (PC 호스트명에 동결) |
| `device_config.site_name` | `신기폐수처리장` |
| `measure_logs_v2` 신규 데이터 | `Site_ID='Shingi'` — 당일 14:29분까지 정상 수신 |
| `measure_logs_v2` 과거 데이터 | `Site_ID='TMSTOC-250701-01'` 1,265건 |

**업로드 자체는 정상이었다.** 대시보드가 두 값을 다르게 쓰는 것이 증상의 실체다
(`dashboard/src/App.jsx`).

- **접속 허가 판정** — `device_config` 를 `or=(site_id.ilike.…, site_name.ilike.…)` 로 조회
  → `?site=신기폐수처리장` 은 통과, `?site=Shingi` 는 차단
- **데이터 조회 필터** — URL 파라미터가 아니라 **`device_config.site_id`** 로
  `measure_logs_v2.Site_ID` 를 필터 → 옛 1,265건만 잡히고 신규 `Shingi` 건은 누락

즉 `device_config.site_id` 한 칸이 접속 경로와 데이터 경로를 동시에 갈라놓고 있었다.

## 2. 업로더 v5.4는 정상 동작했다 (초기 판단 정정)

조사 시점에 `device_config.site_id` 가 여전히 호스트명이어서 **현장에 구버전이 설치된 것으로
추정**하였으나, 오판이었다. 약 15분 뒤 재조회 시 값이 `Shingi` 로 바뀌어 있었다.
v5.4의 `sync_device_config_to_supabase()` 가 **다음 동기화 주기에 스스로 교정**한 것이다
(`gui_uploader.py:869`, 매 동기화 시작 시 호출).

→ **exe 교체는 불필요**했다. 다만 **동기화 주기(기본 15분) 만큼 지연된 뒤 교정**되므로,
현장에서 설정 저장 직후 대시보드를 확인하면 아직 안 고쳐진 것처럼 보인다. 이 점을 인지해야 한다.

## 3. 자동화되지 않은 부분 — 과거 데이터

v5.4가 교정하는 것은 `device_config` 뿐이다. **이미 옛 `Site_ID` 로 적재된 측정 데이터는
그대로 남는다.** 7월 평택 건에서는 시운전 이전 데이터라 이관하지 않기로 결정했으나,
이번 신기 건은 **동일 기기의 정상 운전 데이터**임이 `Device_ID` 로 확인되어 통합하기로 하였다.

### 조치 결과

```
device_config.site_id                    → 'Shingi'  (1건)
measure_logs_v2.Site_ID  'TMSTOC-250701-01' → 'Shingi'  (1,265건)
```

| | 변경 전 | 변경 후 |
|---|---|---|
| `Site_ID='TMSTOC-250701-01'` | 1,265건 | 0건 |
| `Site_ID='Shingi'` | 4건 | **1,269건** |

기간 2025-06-30 10:21 ~ 2026-08-13 15:29 전 구간이 한 지점으로 연결되었다.

**안전 확인**: 옛 `Site_ID` 를 쓰는 다른 기기의 데이터가 0건임을 사전 확인한 뒤 실행하였고,
UPDATE 필터도 `Device_ID=eq.TMSTOC-250701-01` 로 한정하여 타 지점은 건드리지 않았다.

## 4. 산출물

- **`tools/migrate_site_id.py` 신설** — 지점 식별자 교정·통합 도구.
  `device_config` PATCH 와 과거 `measure_logs_v2` 통합을 한 번에 수행하는 멱등 스크립트.
  인자 없이 실행하면 이번 신기 건 기본값, `<device_id> <옛 site_id> <새 site_id>` 로 재사용 가능.
  **옛 Site_ID 를 쓰는 다른 기기 데이터가 있으면 중단**하는 가드를 내장했다(이 검사를 풀지 말 것).
  멱등성은 재실행으로 검증하였다.
- **`docs/ARCHITECTURE.md` 트러블슈팅 표에 2개 증상 행 추가** —
  "사이트 이름으로는 접속되는데 site_id로는 막힘", "최근 데이터만 보이고 과거가 끊김".
- **`계측기_PC_배포패키지_v5.4/uploader_config.json` 에 Supabase 접속 정보 기입** —
  현장 반입 시 URL/Key 를 매번 손으로 넣던 것을 제거. `is_mock` 도 `false` 로 변경.
  `site_id`/`site_name`/`is_paused` 는 Fail-safe 유지를 위해 `auto`/`true` 그대로 둔다.
  `.gitignore` 의 `**/uploader_config.json` 에 걸려 저장소에는 커밋되지 않는다.
  (평문 자격 증명의 현장 PC 배포는 2026-07-27 결정대로 운영상 허용 범위)

## 5. 미처리 (사용자 판단)

- **`TOC-260706-02` / `TOC-260706-03`** — `TOC-260706-03` 의 `site_id` 가 `TOC-260706-02`(타 기기
  지점 ID)로 남아 있으나, **두 기기 모두 현장 가동 전이며 데이터에 문제가 없어 그대로 둔다.**
  현장 설치 시 업로더에서 Site ID 를 지정하면 v5.4 가 자동 교정한다.

## 6. 후속 과제 (2026-07-27 등록분 유지)

- [ ] 자격 증명 재발급 (Supabase / SMTP / Telegram)
- [ ] 업로더 service_role → anon 키 + RLS 전환
- [ ] `sites` 테이블 분리
- [ ] `device_config.is_active` 컬럼 부재
- [ ] `App.jsx` 컴포넌트 분리

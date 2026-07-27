# TOC-850 웹 대시보드 — 시스템 구조 및 지점(Site) 식별 체계

> 이 문서는 **다중 사이트 운영**을 전제로 한 실제 데이터 흐름의 단일 기준 문서입니다.
> 코드를 고칠 때 이 문서와 어긋나면 문서를 먼저 고치고 코드를 맞추십시오.

---

## 1. 전체 구성

```
[현장 계측기 PC]                    [Supabase / PostgreSQL]            [Vercel]
────────────────────                ──────────────────────             ────────────────
TOC-850 계측기
   │ (계측기 소프트웨어가 기록)
   ↓
toc_db.db (SQLite)
   └ Measure_Result_With_
     Channel_Name (View)  ─────┐
                               │
gui_uploader.py                │  ① 측정 데이터 INSERT
  └ uploader_config.json  ─────┼──→  measure_logs_v2
      site_id / device_id      │       (id, Date_Time, Site_ID, Device_ID,
      supabase_url / key       │        Channel, Channel_Name, TOC_Conc, ...)
                               │
                               │  ② 지점/기기 설정 UPSERT
                               └──→  device_config                    dashboard/ (React+Vite)
                                       (device_id PK, site_id,   ←──③ 조회  └ src/App.jsx
                                        site_name, passcode,          api/send-alert.js
                                        toc_alert_high JSONB,         api/telegram-webhook.js
                                        use_single_table)
```

- **①** 15분(기본) 주기로 SQLite View의 신규 행을 증분 조회해 전송. 각 행에 `Site_ID`, `Device_ID`를 삽입합니다.
- **②** 매 동기화 시작 시 및 업로더에서 설정 저장 시, `device_config` 행을 현재 설정과 일치시킵니다(멱등).
- **③** 대시보드는 URL 파라미터로 지점을 특정하고, `device_config`에서 임계값·패스코드·지점명을 읽습니다.

---

## 2. 식별자 체계 — `site_id` vs `device_id`

| 항목 | 의미 | 예시 | 결정 주체 |
|---|---|---|---|
| `site_id` | **지점(사업장) 식별자.** 대시보드 접속 URL의 키 | `Samyang_Incheon`, `Pyeongtaek1` | 사람이 부여 (업로더 UI에서 입력) |
| `device_id` | **계측기 1대의 고유 식별자.** device_config의 PK | `TMSTOC-241224` | 사람이 부여, 미설정 시 PC 호스트명 자동 사용 |
| `site_name` | 화면 표시용 한글 지점명 | `삼양사 인천공장` | 사람이 부여 |

**한 지점(site_id)에 계측기(device_id)가 여러 대 붙을 수 있습니다.** 1:N 관계입니다.

- `?site=<site_id>` → 해당 지점의 **모든 기기** 데이터를 합쳐서 조회
- `?device=<device_id>` → **특정 기기 1대**만 조회

### 접속 URL

```
지점 단위   https://<대시보드주소>/?site=Samyang_Incheon
기기 단위   https://<대시보드주소>/?device=TMSTOC-241224
관리자 모드 https://<대시보드주소>/?site=Samyang_Incheon&admin=true
```

> 파라미터가 전혀 없으면 접속 제한 화면이 표시됩니다. **기본 지점 폴백은 존재하지 않습니다.**

---

## 3. site_id가 원격에 반영되는 경로 (중요)

업로더 UI에서 지점 식별자를 바꾸면 **두 곳**에 반영되어야 하며, 두 경로 모두 코드로 보장됩니다.

| 대상 | 반영 시점 | 담당 코드 |
|---|---|---|
| `measure_logs_v2.Site_ID` | 다음 동기화 시 전송되는 행부터 | `uploader_worker_process()` — 각 행에 `Site_ID` 삽입 |
| `device_config.site_id` | ⓐ 설정 저장 버튼, ⓑ 매 동기화 시작 시 | `sync_device_config_to_supabase()` |

`sync_device_config_to_supabase()`의 동작:

1. `PATCH device_config?device_id=eq.<device_id>` 로 `{site_id, site_name}` 갱신
   (`Prefer: return=representation` 으로 실제 매칭된 행이 있는지 확인)
2. 매칭된 행이 0건이면 → `auto_register_device_config()` 가 기본 임계값과 함께 신규 POST

멱등 연산이므로 매 주기 호출해도 안전합니다.

> ⚠️ **과거 결함(2026-07-27 수정 완료)**
> 이전 코드는 저장 시 `site_name`만 PATCH하고 `site_id`는 보내지 않았습니다. 또한
> `auto_register_device_config()`가 **어디에서도 호출되지 않는 죽은 코드**였습니다.
> 그 결과 `measure_logs_v2.Site_ID`는 바뀌는데 `device_config.site_id`는 최초 등록값
> (대개 PC 호스트명)에 동결되어, 대시보드가 "등록되지 않은 지점 ID"로 접속을 거부했습니다.

---

## 4. 미설정(Fail-safe) 상태 판별

`uploader_config.json`의 `site_id` / `site_name` / `device_id`에는 `"auto"`를 넣어 출고합니다.

`load_config()`는 `"auto"`를 **호스트명으로 즉시 치환**하면서 `is_auto_config = True` 플래그를 세웁니다.
따라서 미설정 여부는 **문자열이 아니라 `is_auto_config` 플래그로만 판별**해야 합니다.

```python
# ❌ 틀림 — load_config에서 이미 호스트명으로 치환되어 절대 참이 되지 않음
if self.site_id.lower() == "auto": ...

# ✅ 맞음
if getattr(self, 'is_auto_config', False): ...
```

`is_auto_config`가 True이면 자동 동기화가 일시정지되고 `device_config` 등록/갱신도 보류됩니다.
현장 엔지니어가 실제 지점 정보를 입력하고 저장하면 해제됩니다.

---

## 5. 신규 사이트 온보딩 절차

1. 계측기 PC에 배포 패키지(`계측기_PC_배포패키지_vX.X/`)를 복사
2. `uploader_config.json`의 `db_path`, `supabase_url`, `supabase_key` 확인
3. 업로더 실행 → 설정 패널에서 입력
   - **지점 식별자 ID (Site ID)** — 영문/숫자/`_`/`-` 만 사용. 대시보드 URL에 그대로 들어감
   - **기기 고유 ID (Device ID)** — 계측기 시리얼 권장
   - **사이트 이름** — 한글 표시명
4. **💾 설정 저장** 클릭 → 로그에 `[원격 설정 동기화]` 또는 `[자동 등록 성공]` 확인
5. `python diagnose_sync.py` 로 자가진단 (Step 2 / 4-2 가 정상인지 확인)
6. `https://<대시보드주소>/?site=<site_id>` 접속 확인 (기본 패스코드 `850`)

### 문제 발생 시 진단

| 대시보드 화면 | 원인 | 조치 |
|---|---|---|
| "대시보드 접속 제한" (🔒) | URL에 `?site=` / `?device=` 파라미터 없음 | 올바른 링크로 접속 |
| "등록되지 않은 … 지점 ID" + **주황색 안내문** | 측정 데이터는 오는데 `device_config` 행이 없음 | 업로더에서 **설정 저장** 1회 실행 |
| "등록되지 않은 … 지점 ID" (안내문 없음) | 해당 ID로 들어온 데이터 자체가 없음 | site_id 오타 확인, 업로더 가동 여부 확인 |
| 데이터 0건인데 접속은 됨 | site_id는 맞으나 전송 실패 | `diagnose_sync.py` Step 3/4 확인 |

---

## 6. 알려진 제약 (미해결)

- **`sites` 테이블 부재** — `site_id` / `site_name` / `passcode` / 임계값이 기기 행마다 중복 저장됩니다.
  같은 지점에 기기가 여러 대면 설정이 서로 어긋날 수 있고, 대시보드는 그중 한 행만 기준으로 삼습니다
  (`?device=` 지정 → 해당 기기 / 미지정 → `site_id` 정확 일치 행 우선).
  근본 해결은 `sites` 테이블 분리이며, 스키마 변경 승인이 필요합니다(`.agents/AGENTS.md` §2 참조).
- **`device_config.is_active` 컬럼 없음** — 대시보드가 `conf.is_active !== false`로 읽어 항상 `true`.
  지점 비활성화 기능은 실질적으로 동작하지 않습니다.
- **`App.jsx` 단일 파일 약 2,900줄** — 데이터 로딩·차트·설정·알림·CSV·관리자 화면이 한 파일에 있습니다.
- **service_role 키 사용** — 업로더가 RLS를 전면 우회하는 키로 접속합니다. anon 키 + INSERT 전용 RLS 정책으로
  전환하는 것이 옳습니다. 아래 §7 참조.

---

## 7. 보안 현황

### ✅ 완료 — GitHub 노출 자격 증명 제거 (2026-07-27)

Supabase service_role 키 · SMTP 비밀번호 · Telegram 봇 토큰이 저장소 여러 파일에 커밋되어 있었습니다
(배포 패키지 config, `TOC850_Company_Handoff/gui_uploader.py` 하드코딩, 과거 `App.jsx`/`scratch_test.js`,
회의록, 통합명세서).

`git filter-repo --replace-text` 로 **전체 117개 커밋을 재작성**하여 플레이스홀더로 치환하고
`origin/main`에 force push 했습니다. 원격 히스토리 전수 검사에서 잔여 0건을 확인했습니다.

### 🔴 미해결 — 자격 증명 재발급

노출 이력이 있으므로 **해당 키들은 유출된 것으로 간주해야 합니다.**
force push 후에도 GitHub는 참조되지 않는 객체를 일정 기간 보관하며 직접 SHA URL로 접근될 수 있고,
기존 clone/fork 사본에도 그대로 남아 있습니다.

1. Supabase API 키 재발급 · SMTP 비밀번호 변경 · Telegram 봇 토큰 재발급
   (재발급 시 전 현장 `uploader_config.json` 갱신 필요)
2. 업로더를 anon 키 + `measure_logs_v2` INSERT / `device_config` UPSERT 전용 RLS 정책으로 전환

> 고객사 계측기 PC에 키가 평문 배포되는 것 자체는 운영상 허용된 방침입니다(2026-07-27 결정).
> 다만 그렇기 때문에 더더욱 service_role이 아닌 최소 권한 키를 써야 합니다.

### 커밋 전 점검

```bash
# .gitignore를 위반하며 추적 중인 파일 확인 (비어 있어야 정상)
git ls-files -i -c --exclude-standard
```

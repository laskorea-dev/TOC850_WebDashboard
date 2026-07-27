# 2026-07-27 · 지점 식별자(site_id) 전파 결함 수정 및 저장소 정리

**참석**: 개발실
**배경**: 현재 1개 사이트(삼양사 인천공장)만 운영 중이나, 곧 타 사이트로 대시보드가 확대 적용될 예정.
업로더에서 지점 식별자(Site ID)를 지정했음에도 대시보드가 이를 인식하지 못하는 문제가 보고됨.

---

## 1. 원인 분석 결과

Supabase 실 데이터 조회로 증상을 재현·확증하였다.

| device_config.device_id | device_config.**site_id** | measure_logs_v2의 **Site_ID** | 판정 |
|---|---|---|---|
| TMSTOC-241224 | `Samyang_Incheon` | `Samyang_Incheon` | 정상 (기존 운영 사이트) |
| TOC-260706-01 | `TOC-260706-01` | **`Pyeongtaek1`** | **불일치** |
| TOC-260706-03 | **`TOC-260706-02`** | `TOC-260706-03` | 교차 오염 |
| TOC-260706-02 | `TOC-260706-02` | `TOC-260706-02` | 호스트명 방치 |
| TMSTOC-250701-01 | `TMSTOC-250701-01` | `TMSTOC-250701-01` | 호스트명 방치 |

측정 데이터에는 새 `Site_ID`가 정상 반영되는데 `device_config.site_id`만 최초 등록값에 동결되어 있었다.

### 근본 원인 (업로더 4건)

1. **`save_config()`가 `site_id`를 서버로 보내지 않음**
   `bg_update_site_name_on_supabase()`의 PATCH payload가 `{"site_name": ...}` 뿐이었다.
2. **`auto_register_device_config()` / `fetch_device_config()`가 죽은 코드**
   정의부와 상호 재귀 호출 외에 어떤 호출 지점도 없었다. → 신규 사이트는 `device_config` 행이 아예 생성되지 않음.
3. **Fail-safe 가드 무력화**
   `load_config()`가 `"auto"`를 호스트명으로 먼저 치환한 뒤,
   `auto_register_device_config()`가 다시 `site_id.lower() == "auto"`를 검사하여 절대 참이 되지 않았다.
   → 미설정 상태의 기기가 **호스트명을 site_id로 등록**해 버린 것이 위 표의 `TOC-260706-0x` 행들이다.
4. `device_config` URL 조립 로직이 3곳에 중복되어 있었다.

### 근본 원인 (대시보드 2건)

5. **`site_config_v2` 폴백이 죽은 경로** — 해당 테이블은 존재하지 않는다
   (`PGRST205: Could not find the table 'public.site_config_v2'`). 항상 404 후 접속 차단으로 직행.
6. **`VITE_SUPABASE_TABLE` 기본값이 `"Samyang_Incheon"` 하드코딩** — 파라미터 누락 시 타 지점 사용자에게
   삼양사 데이터가 노출될 수 있는 다중 사이트 확산 저해 요인.

---

## 2. 조치 내역

### 업로더 (`gui_uploader.py`)

- `sync_device_config_to_supabase()` 신설 — `device_id` 기준 PATCH(`return=representation`으로 매칭 확인)
  후 0건이면 POST 신규 등록하는 **멱등 upsert**.
- 호출 지점 2곳 연결: **설정 저장 시** + **매 동기화 시작 시**(`uploader_worker_process`).
  → 현장에서 저장 버튼 1회로 기존 잘못된 행이 자동 교정된다.
- `auto_register_device_config()` 가드를 문자열 검사 → `is_auto_config` 플래그 검사로 교정.
- `build_device_config_url()` 헬퍼로 URL 조립 3중 중복 제거.
- `bg_update_site_name_on_supabase()` 제거 (상위 함수로 흡수).

### 대시보드 (`dashboard/src/App.jsx`)

- `SUPABASE_TABLE` 하드코딩 상수 제거, `siteSearchTerm` 폴백 제거.
- 죽은 `site_config_v2` 폴백 제거 → **측정 데이터 유무 진단 조회**로 대체.
  `device_config`는 없는데 데이터는 들어오는 경우 접속 차단 화면에
  "업로더에서 설정 저장을 1회 실행하십시오" 안내를 표시한다.
- 한 지점 다중 기기 대응: `?device=` 지정 시 해당 기기 행, 미지정 시 `site_id` **정확 일치** 행 우선 선택
  (기존 `confList[0]` 무조건 선택 → 개선). 2대 이상이면 콘솔에 안내.
- 미정의 변수 `deviceIds` 참조 제거 (테스트 메일 발송 버튼 클릭 시 ReferenceError로 크래시하던 결함).

### 저장소 정리

- `.gitignore` 전면 재작성 — 섹션 정리, `**/uploader_config.json` 추가, `.env.example` 커밋 유지 negation 추가.
- 추적 해제(디스크 파일은 유지): `.vercel/`, `gui_uploader_v5.1.exe`(11MB),
  `chrome_debug.log`, `TOC850_Company_Handoff/.../mock_google_sheet.csv`(3.5MB).
- `docs/ARCHITECTURE.md` 신설 — 구조도, `site_id`/`device_id` 체계, site_id 전파 경로,
  신규 사이트 온보딩 절차, 증상별 트러블슈팅 표, 알려진 제약.
- `README.md` 재작성 — 실제 디렉터리 구조 및 "오해하기 쉬운 항목"(`uploader.py` 미사용,
  `TOC850_Company_Handoff/` 현행 아님) 명시.
- `dashboard/.env.example` 갱신 — service_role 키 금지 경고 및 URL 파라미터 규칙 명시.

---

## 3. GitHub 노출 자격 증명 제거 (완료)

**방침 결정**: 고객사 계측기 PC에 평문 배포되는 것은 운영상 허용. 단, **GitHub 원격 저장소에
노출된 것은 제거**한다.

### 노출 범위 (당초 파악보다 넓었음)

| 비밀정보 | 노출 파일 |
|---|---|
| Supabase **service_role** 키 | `계측기_PC_배포패키지_v5.1/uploader_config.json`, `TOC850_Company_Handoff/gui_uploader.py`(하드코딩), `dashboard/src/App.jsx`(과거), `dashboard/scratch_test.js`(과거) |
| SMTP 비밀번호 | 위 config, `meeting_notes/2026-06-18_alert_and_test_page_design.md` |
| Telegram 봇 토큰 | 위 config, `TOC850_B2B_시스템_통합명세서.md`, `dashboard/api/send-alert.js`(과거), `meeting_notes/2026-07-07_telegram_tuning_and_passcode_change.md` |

### 조치

1. 백업: `git bundle create full-repo-backup.bundle --all` (11.9MB, 전체 ref 보존)
2. 작업트리 정리 — 위 문서/소스의 비밀정보를 플레이스홀더로 치환,
   `계측기_PC_배포패키지_v5.1/uploader_config.json` 추적 해제(디스크 파일은 유지)
3. `git filter-repo --replace-text` 로 **전체 117개 커밋** 재작성
   - service_role 키 → `YOUR_SUPABASE_KEY_HERE`
   - Telegram 토큰 → `<TELEGRAM_BOT_TOKEN>`
   - SMTP 비밀번호 → `<SMTP_PASSWORD>`
4. `origin/main` force push (`a39d728` → `c4f1f3e`, `--force-with-lease` 사용)
   - 트리 차이는 비밀정보 치환 5개 파일뿐 (`git diff --stat a39d728 main`으로 확인)
   - 운영 대시보드 빌드 내용에는 영향 없음
5. 원격 히스토리 전수 재검사 — 3개 문자열 모두 **잔여 0건** 확인

`feature/stage-caution-warning`(이번 site_id 수정 포함)은 AGENTS.md §2 "사용자 최종 확인 전
push 금지" 규칙에 따라 **로컬 커밋으로만 유지**한다.

### 남은 위험 (인지 필요)

- GitHub는 force push 후에도 참조되지 않는 객체를 일정 기간 보관하며, **직접 SHA URL로 접근 가능**할 수 있다.
  완전 제거가 필요하면 GitHub Support에 GC를 요청해야 한다.
- 기존에 clone/fork한 사본에는 그대로 남아 있다.
- 따라서 **해당 키들은 이미 유출된 것으로 간주**해야 하며, 근본 해결은 재발급이다. (아래 후속 과제)

---

## 4. 후속 과제

- [ ] 자격 증명 재발급 — Supabase API 키, SMTP 비밀번호, Telegram 봇 토큰
      (노출 이력이 있으므로 유출 간주. 재발급 시 전 현장 uploader_config.json 갱신 필요)
- [ ] 업로더를 service_role → anon 키 + INSERT/UPSERT 전용 RLS 정책으로 전환
- [ ] `sites` 테이블 분리 — 지점 정보가 기기 행마다 중복되는 구조적 결함 (스키마 변경 승인 필요)
- [ ] `device_config.is_active` 컬럼 부재 — 대시보드가 항상 `true`로 읽어 지점 비활성화 기능 무효
- [ ] `App.jsx` 약 2,900줄 단일 파일 컴포넌트 분리
- [ ] `TOC850_Company_Handoff/` 사본 처리 방침 결정 (보존/삭제)

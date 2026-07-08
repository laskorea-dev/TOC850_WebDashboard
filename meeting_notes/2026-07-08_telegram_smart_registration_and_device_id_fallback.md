# 회의록: 텔레그램 스마트 자가등록 및 대시보드 UI 장비 ID 개선

- **일시**: 2026-07-08
- **참석자**: USER, Antigravity (AI Coding Assistant)
- **주제**: 텔레그램 경보 알림 수신자 스마트 자가등록(하이브리드 ID 지원) 및 대시보드 화면상의 장비 ID 정밀 노출 패치

---

## 1. 요구사항 및 배경
1. **문제 현상**: Uploader PC가 수집 데이터 업로드 시 `Device_ID` 컬럼에 기기 번호 대신 사이트 ID(`Samyang_Incheon`)를 전송하여 대시보드 화면 수신자 목록 타이틀 옆에 사이트 ID가 중복 노출됨.
2. **개선 요구**: 
   - 텔레그램 봇 대화방에서 사용자가 알림 등록을 시도할 때, 기기 고유 ID(`TMSTOC-241224`)와 사이트 ID(`Samyang_Incheon`) 중 **어느 것을 입력해 등록하더라도 자동으로 매핑**되어 등록을 완료하게 함.
   - 대시보드 설정 모달 타이틀 영역에 실질적인 물리 장비 ID(`TMSTOC-241224`)가 올바르게 표현되도록 UI 감지 로직 적용.

---

## 2. 합의된 솔루션 및 구현 세부사항

### A. 텔레그램 Webhook API 양방향 조회 연동 (`/api/telegram-webhook.js`)
- **Supabase OR 조건 쿼리**: 사용자가 `/등록 [입력ID] [사용자명] [패스코드]`를 입력했을 때, `device_config` 조회 시 `or` 필터를 이용하여 `device_id` 혹은 `site_id` 중 어느 쪽에든 매치되는 첫 번째 기기 설정을 찾아내도록 함.
  - 쿼리 예시: `supabaseUrl/device_config?or=(device_id.eq.[입력ID],site_id.eq.[입력ID])`
- **Primary Key 매칭 업데이트**: 조회된 행의 보안 패스코드가 일치하면, 고유 기본키 값인 `deviceConf.device_id` 값을 사용해 PATCH 업데이트를 안전하게 수행.
- **가이드 문구 수정**: `/start` 및 `/등록` 실패 시 나타나는 문구에 디바이스 ID 또는 사이트 ID를 모두 기재하여 자가등록이 가능함을 안내.

### B. 대시보드 장비 ID 폴백 노출 렌더링 (`App.jsx`)
- 최신 수집 데이터에서 파싱한 디바이스 ID 값(`latestLogDeviceId`)이 현재의 사이트 ID(`siteConfig.site_id` - 즉 `Samyang_Incheon`)와 일치할 경우 ➔ DB 설정에 저장된 물리 고유 ID인 **`siteConfig.device_id`**를 디폴트로 노출하도록 개선.
- 만약 컴퓨터가 완전히 교체되어 진짜 신형 기기 ID로 로그 데이터가 올라오기 시작하면 자연스럽게 새 기기 ID가 노출되어 구형/신형 감지가 가능하도록 유지함.

---

## 3. 결과 및 릴리즈 현황
- 대시보드 로컬 컴파일 검증 성공.
- 최신 안정화 코드를 GitHub `main` 브랜치에 병합 후 푸시(`origin/main`) 완료.
- 실서버(`https://toc-850-web-dashboard.vercel.app/`) 및 테스트 서버(`https://dashboard-ochre-two-35.vercel.app/`) 동시 배포 릴리즈 완료.

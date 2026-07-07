# 회의록: Zero-Touch 무설정 장비 등록 및 하드웨어 기반 고유 ID 자동화

* **일시**: 2026-07-07
* **참석자**: USER, Antigravity (AI 코딩 어시스턴트)
* **주제**: 새 장비 및 고객 추가 시 Supabase 설정 등록 수동 오버헤드 제거와 PC 고유 식별자 자동 생성 구현

---

## 1. 결정 사항

### A. Zero-Touch 장비 자동 등록 (Auto-Registration)
* **문제점**: 현장에 새 기기를 깔 때마다 관리자가 Supabase 웹 콘솔에 수동으로 접속하여 `850_dashboard_site_config` 테이블에 설정 행(Row)을 추가해 주어야 하는 번거로움과 입력 실수 가능성이 존재함.
* **해결책**:
  * 업로더가 구동될 때 Supabase에서 현재 장비 ID(`device_id`)용 설정을 조회(GET)합니다.
  * 만약 등록된 설정이 없어 비어있는 것으로 확인되면, **업로더 프로그램이 스스로 Supabase에 기본 설정값들을 채워 새 행을 즉시 자동 등록(POST)**합니다.
  * 기본 설정값에는 `use_single_table: true` 플래그, 초기 패스코드 `"850"`, 각 채널별 기본 경고 기준값이 포함됩니다.

### B. PC 하드웨어 기반 고유 ID 자동 생성 (Auto Device ID)
* **문제점**: 기기 배포 시마다 설정 파일(`uploader_config.json`)을 직접 열어 기기명을 일일이 수정해주어야 하며, 중복 ID 입력 오류의 여지가 있음.
* **해결책**:
  * 설정 파일의 `"device_id"` 값이 비어있거나 `"auto"`로 설정되어 있을 경우, 프로그램이 실행 중인 Windows 장치 이름(Hostname)을 자동으로 조회합니다.
  * 조회된 컴퓨터 이름을 기반으로 고유한 하드웨어 식별자(예: `TOC-PC-01`)를 자동 발급하여 사용합니다.

### C. 웹 대시보드 식별자 분리 (Site & Device URL Parameter Separation)
* **결정 사항**: 고객 접속용 명칭(`site`)과 계측기 실제 장치 고유 ID(`device`)를 URL 파라미터 수준에서 완전 분리합니다.
* **해결책**:
  1. **보안 및 설정 로드 (`?site=`)**: 대시보드의 기본 설정(비밀번호, 임계치 등)을 가져오기 위한 키워드로 `site`를 사용합니다. DB에서 `site_id` 또는 `site_name`이 `site` 값과 일치하는 행을 조회합니다.
  2. **데이터 쿼리 필터 (`?device=`)**: 차트에 표시할 실제 데이터의 `Device_ID` 식별자로 `device` 파라미터를 사용합니다.
  3. **유연한 폴백 연동**:
     * `device` 파라미터가 명시적으로 URL에 입력된 경우 (예: `?site=삼양사_인천&device=TOC-PC-02`), DB 설정값과 상관없이 `TOC-PC-02` 장치의 데이터를 조회합니다. (하드웨어 교체 테스트에 유용)
     * `device` 파라미터가 생략된 경우 (예: `?site=삼양사_인천`), DB에 등록된 지점의 기본 장치 식별자(`siteConfig.site_id` 즉 `TOC-PC-01`) 데이터를 기본 조회합니다.
     * 납품처 결정 전 테스트 시 (예: `?device=TOC-PC-01` 단독 입력), 장치 고유 ID를 기준으로 설정을 조회하고 해당 데이터를 즉시 쿼리합니다.

---

## 2. 구현 결과 요약

1. **`gui_uploader.py` 수정**:
   * `get_unique_device_id` 메소드 구현: Windows 장치 이름(Hostname) 조회 및 정제 로직 구현.
   * `load_config` 수정: `"device_id"`가 `"auto"`이거나 비어있을 시 컴퓨터 이름으로 대체 로드.
   * `auto_register_site_config` 메소드 구현: Supabase 설정 부재 시 신규 행 기본값 삽입 API 연동.
   * `fetch_site_config` 수정: 설정 부재 시 1회 자동 등록을 즉시 수행하도록 재귀 핸들링(무한 루프 방지 장치 포함).
2. **`App.jsx` & `LegacyApp.jsx` 수정**:
   * URL에서 `site`와 `device` 파라미터를 파싱하여 `siteSearchTerm` 및 `deviceIdParam` 변수로 연동.
   * 설정 조회 시 `siteSearchTerm` 기준 `OR` 쿼리(`site_id` 또는 `site_name`)로 설정 로딩.
   * 데이터 조회(`loadData`), 모의 데이터 생성/삭제, CSV 다운로드 시 `device` 파라미터가 존재하면 우선 쿼리하고, 없을 시 DB에 기록된 `siteConfig.site_id`로 자동 매칭해 단일/개별 테이블 분기 조회.
   * 대시보드 복귀(handleReturnToDashboard) 시 두 파라미터 상태를 모두 유지하며 이동하게 처리.


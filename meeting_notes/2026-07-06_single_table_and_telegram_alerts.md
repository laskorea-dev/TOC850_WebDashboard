# 회의록: 단일 테이블 통합 및 텔레그램 무료 푸시 알림 연동

* **일시**: 2026-07-06
* **참석자**: USER, Antigravity (AI 코딩 어시스턴트)
* **주제**: 장비 추가 시 테이블 생성 비효율성 제거 및 텔레그램 기반 무료 다대다(Many-to-Many) 푸시 알림 연동 구현

---

## 1. 결정 사항

### A. 데이터베이스 단일 테이블 통합 (Single-Table Architecture)
* **문제점**: 장비(Device)가 추가될 때마다 Supabase에서 테이블을 개별적으로 생성하여 관리 오버헤드가 크고 스케일링이 어려움.
* **해결책**:
  * 모든 장비가 데이터 전송 타겟으로 단일 테이블(기본값: `measure_logs`)을 사용하도록 통합.
  * 기존 테이블 구조에 존재하던 `Device_ID` 컬럼을 기본 필터링 수단으로 활용.
  * 데이터 적재(POST), 최신 시각 조회(GET), 삭제(DELETE) 요청 시 모두 `Device_ID = siteId` 조건 필터를 필수적으로 주입하도록 리팩토링.
  * 하위 호환성을 완벽히 유지하여, 개별 테이블 모드와 단일 테이블 모드(`VITE_USE_SINGLE_TABLE === 'true'`)를 환경 변수 설정에 따라 자유롭게 선택할 수 있게 지원.

### B. 텔레그램 무료 다대다 푸시 알림 연동
* **문제점**: SMTP 메일 알림 외에 모바일 기기로 무료로 실시간 메시지를 받아볼 수 있는 창구 필요. 여러 장비에서 여러 엔지니어 및 단톡방으로 메시지가 가야 하는 다대다 조건 만족 필요.
* **해결책**:
  * 텔레그램 봇 API를 활용한 `TelegramAlertSender` 모듈 신규 구현 (`alerts/telegram_sender.py`).
  * 봇 토큰과 Chat ID 목록(개인 및 단톡방 ID 포함, 쉼표 구분)을 통한 메시지 일괄 발송 구현.
  * 텔레그램 메시지 포맷에 최적화된 HTML-to-Telegram text 파서 구현 (안전한 HTML 태그 외 일반 태그는 자동 제거).
  * **스키마 변경 없음 규칙 준수**: 텔레그램 연동 설정을 저장하기 위해 테이블 컬럼을 늘리지 않고, 기존 `850_dashboard_site_config` 테이블의 `toc_alert_high` JSONB 컬럼 내에 `telegram_chat_ids` 및 모의 발송용 테스트 트리거 플래그(`trigger_test_telegram`)를 매립 저장.

---

## 2. 구현 결과 요약

1. **`alerts/telegram_sender.py` 생성**: urllib 기반 무의존성 텔레그램 발송 모듈 구현 완료.
2. **`alerts/__init__.py` 수정**: `alert_type="telegram"` 지원을 위한 팩토리 바인딩 완료.
3. **`gui_uploader.py` 수정**:
   * 최신 업로드 시각 조회 쿼리에 `Device_ID` 필터 반영.
   * `check_and_send_alerts` 함수에서 알림 수신 대상(이메일/텔레그램)의 분기 처리 지원.
   * 웹 대시보드 연동 테스트용 플래그 감지 기능을 `bg_check_test_alert_trigger`로 확장하여 텔레그램 테스트 메시지 실시간 발송 및 플래그 초기화 연동 구현 완료.
4. **`dashboard/src/App.jsx` & `LegacyApp.jsx` 수정**:
   * 단일 테이블 모드 가동을 위한 REST API 쿼리 매핑 및 `Device_ID` 필터 조건 적용.
   * 설정 모달 내 텔레그램 Chat ID 입력 폼 제공 및 Supabase PATCH 저장 연동.
   * Admin 모드에서의 "테스트 텔레그램 발송" 트리거 및 비동기 발송 검증 기능 구현 완료.

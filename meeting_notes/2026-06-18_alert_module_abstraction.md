# 회의록: 알람 전송 모듈 추상화 및 격리 설계 반영

**일시**: 2026년 6월 18일  
**참석자**: 에이전트(Antigravity), 사용자  
**주제**: MMS/카카오톡 등 향후 알람 다각화를 고려한 이메일 알람 기능의 모듈화 및 추상화

---

## 1. 배경 및 요구사항
- 현재 시스템의 경고 발생 시 알람 처리는 이메일(SMTP)로만 한정되어 있으며, `gui_uploader.py` 내부에 하드코딩되어 결합도가 높음.
- 향후 현장 요구사항 및 가용 조건에 따라 MMS 알람이나 카카오톡 알람 기능의 추가 도입을 검토 중.
- 새로운 알람 발송 모듈이 개발되었을 때, 메인 업로더 로직을 수정하지 않고 설정 변경만으로 모듈을 통째로 교체(`Plug & Play`)할 수 있는 유연한 구조 설계가 요구됨.

## 2. 주요 설계 결정 사항
1. **인터페이스 분리 (Base Interface)**:
   - `BaseAlertSender` 추상 베이스 클래스를 정의하여 공통 규격(`send_alert(recipients, subject, body)`)을 수립함.
2. **패키지 분리 (`alerts/` 패키지 구축)**:
   - 메인 프로그램과 강결합을 해소하기 위해 `alerts/` 패키지를 신규 구성함.
   - 기존의 이메일 SMTP 연동 로직은 `alerts/email_sender.py` 의 `EmailAlertSender` 클래스로 이전함.
3. **팩토리 패턴 활용**:
   - `alerts/__init__.py`에 `get_alert_sender(alert_type, **kwargs)` 팩토리 메서드를 구현하여 설정값에 기반한 알람 전송 인스턴스 동적 로딩을 지원함.
4. **설정 동적 연동**:
   - `uploader_config.json` 설정에 `"alert_type"` 키를 지원하며, 기재되지 않거나 비었을 경우 기본값은 `"email"`(이메일 발송)로 자동 대체 적용함.
   - 메인 프로그램(`gui_uploader.py`) 기동 시 해당 인스턴스를 빌드 및 갱신하여 알람 경고 초과 여부 검사 로직 및 웹 연동 테스트 발송 로직에서 호출되도록 리팩토링함.

## 3. 구현 내용 및 결과
- **alerts 패키지 작성 완료**:
  - `alerts/base.py` (추상 기본 클래스)
  - `alerts/email_sender.py` (SMTP 이메일 발송)
  - `alerts/__init__.py` (객체 생성 팩토리)
- **gui_uploader.py 연동 완료**:
  - `smtplib`, `email` 직접 임포트 종속성 제거.
  - `check_and_send_alerts` 및 `bg_check_test_email_trigger`에서 `self.alert_sender.send_alert`로 호출 대체 완료.
- **설정 파일 갱신 완료**:
  - `uploader_config.json`, `uploader_config.example.json`에 `alert_type` 예시 필드 적용 완료.
- **아키텍처 문서 및 투두리스트 최신화 완료**:
  - `1_작업계획서_System_Architecture.md`, `2_투두리스트_Task_List.md`, `3_히스토리_및_완료보고서.md` 갱신 완료.

## 4. 향후 조치 사항
- MMS 또는 카카오톡 알람 기능 연동 조건 충족 시 `alerts/` 하위에 새로운 발송 모듈(예: `alerts/kakao_sender.py`)을 추가 구현하고, `alerts/__init__.py` 팩토리 분기점에 등록한 뒤 `uploader_config.json`의 `"alert_type"`을 `"kakao"`로 변경하여 운영함.

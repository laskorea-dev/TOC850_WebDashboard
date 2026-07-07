# 회의록: 현장 판넬 PC 고지연 네트워크 대응 및 SSL 핸드셰이크 예외 완화

* **일시**: 2026년 7월 7일
* **참석자**: 사용자 (USER), AI 에이전트 (Antigravity)
* **주제**: 판넬 PC 환경에서의 SSL 핸드셰이크 타임아웃 오류 해결 및 연결 신뢰성 강화

---

## 1. 문제 현황 및 원인 분석
* **현상**: 현장 판넬 PC에서 가동 및 저장 수행 시 `urlopen error _ssl.c:975: The handshake operation timed out` 오류가 비주기적으로 발생하고, 일부 API 요청은 가동되지만 실제 `measure_logs_v2` 테이블 데이터 업로드가 진행되지 않는 문제가 발견되었습니다.
* **원인**:
  * 현장 판넬 PC가 사용하는 전용망(VPN 등) 또는 방화벽 SSL 검사 등으로 인해 HTTPS 최초 연결 및 SSL 핸드셰이크에 필요한 왕복 시간(RTT)이 증가했습니다.
  * 기존 업로더에 설정된 API 타임아웃(5초 ~ 8초)이 이러한 RTT를 견디지 못하고 핸드셰이크 지연 중 연결을 강제 차단하여 발생했습니다.

---

## 2. 해결 및 조치 사항
1. **공통 HTTPS API 호출용 `make_supabase_request` 헬퍼 모듈 구축**:
   * API 호출이 실패할 경우, 즉시 전체 프로세스를 무산시키지 않고 **1.5초 간격으로 최대 3회 재시도(Retry)**를 수행하는 복원력 코드를 탑재했습니다.
2. **타임아웃 임계값 상향 조정 (30초)**:
   * 연결 초기화 및 패킷 손실이 잦은 외부망 특성을 반영하여 타임아웃 제한 시간을 기존 5~8초에서 **30초**로 대폭 완화했습니다.
3. **업로더 내 모든 Supabase REST API 통신 마이그레이션**:
   * `query_server_latest_datetime` (서버 시각 조회)
   * `process_real_supabase` (TOC 데이터 벌크 업로드)
   * `fetch_site_config` (사이트 설정 실시간 갱신)
   * `auto_register_site_config` (사이트 자동 등록)
   * `bg_update_site_name_on_supabase` (사이트 한글명 동적 갱신)
   * `bg_check_test_alert_trigger` (테스트 메일 플래그 업데이트 및 리셋)
   * 위의 모든 Supabase 통신 구간에 해당 재시도 및 30초 타임아웃 헬퍼를 적용하여 통신 신뢰도를 극대화했습니다.
4. **Supabase DDL 불일치 및 400 Bad Request 해결**:
   * 로컬 SQLite 뷰에는 존재하지만, Supabase `measure_logs_v2` DDL에는 정의되어 있지 않은 `MAXR` 항목을 JSON 데이터 페이로드에서 사전 제외 처리하여 `400 Bad Request` 에러를 최종 제거했습니다.
5. **컨트롤 버튼 레이아웃 클리핑 해결**:
   * 해상도 및 배율에 따라 `[즉시 동기화]` 및 `[일시정지]` 버튼이 하단 밖으로 가려지는 문제를 막기 위해 Bottom Controls Frame을 `side=tk.BOTTOM`으로 우선 배치하여 컨트롤 패널의 시인성을 항시 보장했습니다.

---

## 3. 빌드 및 배포 패키지 업데이트
* 리팩토링된 코드를 기반으로 단일 실행 바이너리 **`gui_uploader_v5.1.exe`**를 새롭게 재빌드(PyInstaller)하고, 배포 디렉토리(`계측기_PC_배포패키지_v5.1`)에 최종 복사 완료했습니다.

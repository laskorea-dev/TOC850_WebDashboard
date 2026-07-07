# 회의록 (Meeting Notes) - 2026-07-07 (2차)

## 1. 개요 및 안건
* **일자**: 2026-07-07 (2차 회의)
* **안건**: Supabase 원격 설정 테이블 구조 개편을 통한 다중 기기 독립 설정 격리 모델(V3) 정비 및 대시보드 URL 조건별(?site=, ?device=) 라우팅 쿼리 분기 구현

## 2. 결정 사항 및 구조 개편 사양
1. **기기 고유 설정 테이블(`device_config`) 신설**:
   * 기존의 지점 단위 테이블(`site_config_v2`) 구조는 삭제 처리하고, 각 물리 계측기 PC를 고유하게 격리 관리할 수 있도록 **`device_id`를 기본 키(PK)로 하는 `device_config` 테이블**을 신설합니다.
   * `device_config` 테이블은 기기 ID별로 소속 지점 ID(`site_id`), 지점 한글명(`site_name`), 패스코드, 임계치 등을 완전히 격리 보관합니다.
2. **웹 대시보드 데이터 조회 분기 쿼리 구현**:
   * **`?device=기기ID`**로 접속 시: 대시보드 뷰 및 증분점 조회는 `measure_logs_v2` 테이블의 **`Device_ID`** 컬럼을 필터링하여 기기 단위 독립 시계열 데이터만 표현합니다.
   * **`?site=지점ID`**로 접속 시: 대시보드 뷰는 `measure_logs_v2` 테이블의 **`Site_ID`** 컬럼을 필터링하여 해당 지점 하위의 모든 기기 데이터를 통합하여 연속적인 추세선으로 표현합니다.
3. **업로더 프로그램 기준점 기기 일치**:
   * 증분 쿼리(`query_server_latest_datetime`) 기준 필터를 지점코드(`Site_ID`)에서 기기 ID(`Device_ID`)로 변경하여 다중 기기 환경에서 동기화 중첩이나 데이터 누락 문제를 완벽히 방지합니다.

## 3. 실행이 필요한 Supabase DDL SQL 가이드
사용자가 Supabase SQL Editor에서 실행할 스키마 교체 DDL입니다:

```sql
-- 1. 기존 site_config_v2 테이블 삭제
DROP TABLE IF EXISTS public.site_config_v2;

-- 2. device_id를 기본키(PK)로 하는 신규 device_config 테이블 생성
CREATE TABLE public.device_config (
    device_id text NOT NULL PRIMARY KEY,            -- 기기 고유 식별자 (예: TOC-260706-03)
    site_id text NOT NULL,                          -- 기기가 속한 지점 코드 (예: Samyang_Incheon)
    site_name text NOT NULL,                        -- 지점 한글명 (예: 삼양사 인천공장)
    passcode text NOT NULL DEFAULT '850',           -- 대시보드 패스코드
    alert_emails text NULL,                         -- 수신 이메일 리스트 (콤마 구분)
    telegram_chat_ids text NULL,                    -- 수신 텔레그램 Chat ID 리스트 (콤마 구분)
    toc_alert_high jsonb NULL,                      -- 임계치 설정 및 기타 알림 플래그 JSON
    use_single_table boolean NOT NULL DEFAULT true,  -- 단일 테이블 사용 여부
    created_at timestamp with time zone NOT NULL DEFAULT now()
);

-- 3. measure_logs_v2 조회 속도 최적화를 위한 Device_ID 인덱스 추가
CREATE INDEX IF NOT EXISTS idx_measure_logs_v2_device_id ON public.measure_logs_v2("Device_ID");
```

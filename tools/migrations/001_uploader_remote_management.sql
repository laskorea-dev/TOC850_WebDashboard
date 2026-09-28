-- ═══════════════════════════════════════════════════════════════════════
--  업로더 원격 관리 — device_config 원격 제어 컬럼
--
--  Supabase 대시보드 → SQL Editor 에 붙여넣고 실행하십시오.
--  모두 IF NOT EXISTS 이므로 여러 번 실행해도 안전합니다.
--
--  ⚠️ 적용 순서에 제약이 없습니다. 업로더 v5.5 이상은 이 컬럼들이 없어도
--     정상 동작하며(값이 없으면 기존 동작 유지), 컬럼이 생기는 즉시
--     다음 동기화 주기부터 원격 제어가 적용됩니다.
--
--  ⚠️ 2026-09-28: 자가 업데이트용 target_version 과 uploader_release 는
--     002_uploader_self_update.sql 로 분리했다. service_role 키가 공개 번들에
--     노출된 동안 그 둘이 서버에 있으면 현장 PC 에 임의 실행파일을 설치할 수
--     있으므로, 키 재발급(인계 문서 §1.4) 이후에만 적용한다.
-- ═══════════════════════════════════════════════════════════════════════

-- ── 1. 지점별 원격 제어 ────────────────────────────────────────────────
ALTER TABLE public.device_config
  ADD COLUMN IF NOT EXISTS remote_paused    boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS interval_seconds integer,
  ADD COLUMN IF NOT EXISTS notice           text;

COMMENT ON COLUMN public.device_config.remote_paused IS
  'true 로 두면 해당 기기의 동기화가 다음 주기부터 중지된다. 사고 시 긴급 차단용.';
COMMENT ON COLUMN public.device_config.interval_seconds IS
  '동기화 주기(초) 원격 지정. NULL 이면 현장 설정을 따른다. 60 미만은 무시된다.';
COMMENT ON COLUMN public.device_config.notice IS
  '현장 업로더 로그창에 표시할 공지 문구.';

-- ═══════════════════════════════════════════════════════════════════════
--  사용 예시
-- ═══════════════════════════════════════════════════════════════════════

-- (1) 긴급 정지 — 특정 지점
-- UPDATE public.device_config SET remote_paused = true WHERE site_id = 'jeomchon';  -- site_id 는 대소문자 구분

-- (2) 긴급 정지 — 전체
-- UPDATE public.device_config SET remote_paused = true;

-- (3) 해제
-- UPDATE public.device_config SET remote_paused = false;

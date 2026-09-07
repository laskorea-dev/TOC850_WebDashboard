-- ═══════════════════════════════════════════════════════════════════════
--  업로더 원격 관리 — device_config 제어 컬럼 및 배포 정보 테이블
--
--  Supabase 대시보드 → SQL Editor 에 붙여넣고 실행하십시오.
--  모두 IF NOT EXISTS 이므로 여러 번 실행해도 안전합니다.
--
--  ⚠️ 적용 순서에 제약이 없습니다. 업로더 v5.5 는 이 컬럼들이 없어도
--     정상 동작하며(값이 없으면 기존 동작 유지), 컬럼이 생기는 즉시
--     다음 동기화 주기부터 원격 제어가 적용됩니다.
-- ═══════════════════════════════════════════════════════════════════════

-- ── 1. 지점별 원격 제어 ────────────────────────────────────────────────
ALTER TABLE public.device_config
  ADD COLUMN IF NOT EXISTS remote_paused    boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS interval_seconds integer,
  ADD COLUMN IF NOT EXISTS notice           text,
  ADD COLUMN IF NOT EXISTS target_version   text;

COMMENT ON COLUMN public.device_config.remote_paused IS
  'true 로 두면 해당 기기의 동기화가 다음 주기부터 중지된다. 사고 시 긴급 차단용.';
COMMENT ON COLUMN public.device_config.interval_seconds IS
  '동기화 주기(초) 원격 지정. NULL 이면 현장 설정을 따른다. 60 미만은 무시된다.';
COMMENT ON COLUMN public.device_config.notice IS
  '현장 업로더 로그창에 표시할 공지 문구.';
COMMENT ON COLUMN public.device_config.target_version IS
  '이 기기가 올라가야 할 버전. 현재 버전보다 높을 때만 자가 업데이트가 수행된다.';

-- ── 2. 배포 정보 ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.uploader_release (
  version    text PRIMARY KEY,
  url        text NOT NULL,          -- HTTPS 주소여야 한다 (업로더가 검증)
  sha256     text NOT NULL,          -- 소문자 16진수 64자
  notes      text,
  is_active  boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.uploader_release IS
  '업로더 배포 파일 목록. 업로더는 device_config.target_version 과 일치하고 is_active 인 행만 내려받는다.';

-- 업로더는 anon 키로 접속한다. 배포 정보는 읽기만 허용한다.
GRANT SELECT ON public.uploader_release TO anon;


-- ═══════════════════════════════════════════════════════════════════════
--  사용 예시
-- ═══════════════════════════════════════════════════════════════════════

-- (1) 긴급 정지 — 특정 지점
-- UPDATE public.device_config SET remote_paused = true WHERE site_id = 'JEOMCHON';

-- (2) 긴급 정지 — 전체
-- UPDATE public.device_config SET remote_paused = true;

-- (3) 해제
-- UPDATE public.device_config SET remote_paused = false;

-- (4) 새 버전 등록
-- INSERT INTO public.uploader_release (version, url, sha256, notes) VALUES
--   ('5.6',
--    'https://.../gui_uploader_v5.6.exe',
--    '<sha256 소문자 64자>',
--    '증분 기준점 보강');

-- (5) 한 지점에만 먼저 배포 (단계 배포 — 반드시 이렇게 시작할 것)
-- UPDATE public.device_config SET target_version = '5.6' WHERE site_id = 'JEOMCHON';

-- (6) 문제 없으면 전체 배포
-- UPDATE public.device_config SET target_version = '5.6';

-- (7) 배포 중단 (아직 안 받은 지점만 멈춘다. 이미 올라간 지점은 그대로다)
-- UPDATE public.uploader_release SET is_active = false WHERE version = '5.6';

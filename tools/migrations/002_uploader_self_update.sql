-- ═══════════════════════════════════════════════════════════════════════
--  업로더 자가 업데이트 — target_version 컬럼 및 배포 정보 테이블
--
--  ⛔ 적용 금지 조건: service_role 키가 재발급되기 전 (인계 문서 §1.4)
--     업로더는 다운로드 URL 과 SHA256 을 모두 이 테이블에서 읽고 서명을
--     검증하지 않는다. 유출된 키로 이 테이블에 쓸 수 있으면 현장 PC 에
--     임의 실행파일이 설치된다.
--
--  001 에서 분리 (2026-09-28). 모두 IF NOT EXISTS 이므로 반복 실행 안전.
-- ═══════════════════════════════════════════════════════════════════════

ALTER TABLE public.device_config
  ADD COLUMN IF NOT EXISTS target_version text;

COMMENT ON COLUMN public.device_config.target_version IS
  '이 기기가 올라가야 할 버전. 현재 버전보다 높을 때만 자가 업데이트가 수행된다.';

-- ── 배포 정보 ───────────────────────────────────────────────────────
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

-- 업로더는 service_role 로 접속하므로 RLS 를 우회해 읽는다.
-- anon·authenticated 는 조회만 허용하고 쓰기 권한은 회수한다.
-- (Supabase 는 public 스키마 신규 테이블에 anon 쓰기 권한을 기본 부여한다)
ALTER TABLE public.uploader_release ENABLE ROW LEVEL SECURITY;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.uploader_release FROM anon, authenticated;
GRANT SELECT ON public.uploader_release TO anon, authenticated;
DROP POLICY IF EXISTS "read uploader_release" ON public.uploader_release;
CREATE POLICY "read uploader_release" ON public.uploader_release
  FOR SELECT TO anon, authenticated USING (true);


-- ═══════════════════════════════════════════════════════════════════════
--  사용 예시
-- ═══════════════════════════════════════════════════════════════════════

-- (4) 새 버전 등록
-- INSERT INTO public.uploader_release (version, url, sha256, notes) VALUES
--   ('5.6',
--    'https://.../gui_uploader_v5.6.exe',
--    '<sha256 소문자 64자>',
--    '증분 기준점 보강');

-- (5) 한 지점에만 먼저 배포 (단계 배포 — 반드시 이렇게 시작할 것)
-- UPDATE public.device_config SET target_version = '5.6' WHERE site_id = 'jeomchon';

-- (6) 문제 없으면 전체 배포
-- UPDATE public.device_config SET target_version = '5.6';

-- (7) 배포 중단 (아직 안 받은 지점만 멈춘다. 이미 올라간 지점은 그대로다)
-- UPDATE public.uploader_release SET is_active = false WHERE version = '5.6';

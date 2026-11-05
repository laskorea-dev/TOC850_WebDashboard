-- 003_dashboard_read_only.sql
-- 목적: 대시보드가 anon 키로 조회할 수 있게 하고, anon 의 쓰기 권한을 없앤다.
-- 상태: 2026-11-05 적용 (Supabase SQL Editor, 프로덕션)
--
-- 업로더·서버 API 는 service_role 이므로 RLS 와 아래 revoke 의 영향을 받지 않는다.
-- 대시보드가 아직 service_role 로 접속 중이어도 이 SQL 은 동작을 바꾸지 않는다.
--
-- 남는 위험: device_config 의 passcode 와 toc_alert_high.telegram_bot_token 은 anon 으로도 읽힌다.
-- 접속 화면이 브라우저에서 패스코드를 대조하기 때문이며, 이후 단계에서 서버 검증으로 옮겨 막아야 한다.
--
-- 되돌리기:
--   drop policy "anon read measure_logs_v2" on public.measure_logs_v2;
--   drop policy "anon read device_config" on public.device_config;

begin;

alter table public.measure_logs_v2 enable row level security;
alter table public.device_config   enable row level security;

grant select on public.measure_logs_v2 to anon;
grant select on public.device_config   to anon;

revoke insert, update, delete, truncate on public.measure_logs_v2 from anon, authenticated;
revoke insert, update, delete, truncate on public.device_config   from anon, authenticated;

drop policy if exists "anon read measure_logs_v2" on public.measure_logs_v2;
create policy "anon read measure_logs_v2"
  on public.measure_logs_v2 for select to anon using (true);

drop policy if exists "anon read device_config" on public.device_config;
create policy "anon read device_config"
  on public.device_config for select to anon using (true);

commit;

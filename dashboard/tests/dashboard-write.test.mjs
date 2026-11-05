// api/ 아래에 두면 Vercel 이 서버 함수로 배포하므로 tests/ 에 둔다.
import assert from 'node:assert/strict';
import { beforeEach, test } from 'node:test';
import handler from '../api/dashboard-write.js';

const SERVICE_KEY = 'test-service-key';
const device = {
  device_id: 'DEV-1',
  site_id: 'SITE-1',
  passcode: '1234',
  remote_paused: false,
  toc_alert_high: {
    telegram_bot_token: 'old-token',
    receivers: [{ name: '김', value: '111', type: 'telegram' }],
  },
};

let requests;
let rows;

beforeEach(() => {
  process.env.SUPABASE_URL = 'https://example.supabase.co/rest/v1/';
  process.env.SUPABASE_SERVICE_ROLE_KEY = SERVICE_KEY;
  delete process.env.SUPABASE_MEASUREMENT_TABLE;
  delete process.env.SUPABASE_KEY;
  requests = [];
  rows = [device];
  globalThis.fetch = async (url, init = {}) => {
    const method = init.method || 'GET';
    requests.push({ url, method, body: init.body ? JSON.parse(init.body) : undefined, headers: init.headers });
    return method === 'GET' ? new Response(JSON.stringify(rows), { status: 200 }) : new Response(null, { status: 204 });
  };
});

async function call(body, method = 'POST') {
  const out = { status: 0, json: null };
  const res = {
    status(code) {
      out.status = code;
      return this;
    },
    json(value) {
      out.json = value;
      return this;
    },
  };
  await handler({ method, body }, res);
  return out;
}

const writes = () => requests.filter((r) => r.method !== 'GET');
const auth = { device_id: 'DEV-1', passcode: '1234' };

test('POST 외 메서드는 거부한다', async () => {
  assert.equal((await call({}, 'GET')).status, 405);
});

test('목록에 없는 action 은 DB 에 닿기 전에 거부한다', async () => {
  for (const action of ['drop_table', 'constructor', undefined]) {
    assert.equal((await call({ ...auth, action })).status, 400);
  }
  assert.equal(requests.length, 0);
});

test('패스코드가 틀리면 쓰지 않는다', async () => {
  const out = await call({ device_id: 'DEV-1', passcode: 'wrong', action: 'delete_mock' });
  assert.equal(out.status, 401);
  assert.equal(writes().length, 0);
});

test('없는 기기와 틀린 패스코드를 같은 응답으로 돌려준다', async () => {
  const wrong = await call({ device_id: 'DEV-1', passcode: 'wrong', action: 'delete_mock' });
  rows = [];
  const missing = await call({ device_id: 'NOPE', passcode: '1234', action: 'delete_mock' });
  assert.deepEqual(missing, wrong);
});

test('패스코드가 비어 있는 기기는 화면과 같은 기본값으로 대조한다', async () => {
  rows = [{ ...device, passcode: null }];
  assert.equal((await call({ device_id: 'DEV-1', passcode: '850', action: 'delete_mock' })).status, 200);
  assert.equal((await call({ device_id: 'DEV-1', passcode: '', action: 'delete_mock' })).status, 401);
});

test('서버 환경변수가 없으면 500 이고 설정 이름을 노출하지 않는다', async () => {
  delete process.env.SUPABASE_SERVICE_ROLE_KEY;
  const out = await call({ ...auth, action: 'delete_mock' });
  assert.equal(out.status, 500);
  assert.doesNotMatch(out.json.error, /SUPABASE/);
});

test('서버 키는 기존 API 와 같이 SUPABASE_KEY 로도 읽는다', async () => {
  delete process.env.SUPABASE_SERVICE_ROLE_KEY;
  process.env.SUPABASE_KEY = 'fallback-key';
  assert.equal((await call({ ...auth, action: 'delete_mock' })).status, 200);
  assert.equal(writes()[0].headers.Authorization, 'Bearer fallback-key');
});

test('save_config 는 허용한 컬럼만 쓴다', async () => {
  const out = await call({
    ...auth,
    action: 'save_config',
    toc_alert_high: { a: 1 },
    telegram_chat_ids: '1,2',
    alert_emails: 'a@b.co',
    site_name: '지점',
    new_passcode: '9999',
    remote_paused: true,
    interval_seconds: 1,
    device_config: { site_id: 'x' },
  });
  assert.equal(out.status, 200);
  const [patch] = writes();
  assert.equal(patch.method, 'PATCH');
  assert.match(patch.url, /device_config\?device_id=eq\.DEV-1$/);
  assert.deepEqual(patch.body, {
    toc_alert_high: { a: 1 },
    telegram_chat_ids: '1,2',
    alert_emails: 'a@b.co',
    site_name: '지점',
    passcode: '9999',
  });
  assert.equal(patch.headers.Authorization, `Bearer ${SERVICE_KEY}`);
});

test('save_config 는 패스코드 입력이 없으면 패스코드를 건드리지 않는다', async () => {
  assert.equal((await call({ ...auth, action: 'save_config', toc_alert_high: {} })).status, 200);
  assert.deepEqual(writes()[0].body, { toc_alert_high: {} });
});

test('save_config 는 잘못된 형식을 거부한다', async () => {
  for (const toc_alert_high of [null, 'x', [1]]) {
    assert.equal((await call({ ...auth, action: 'save_config', toc_alert_high })).status, 400);
  }
  const long = await call({ ...auth, action: 'save_config', toc_alert_high: {}, site_name: 'x'.repeat(501) });
  assert.equal(long.status, 400);
  assert.equal(writes().length, 0);
});

test('add_receiver 는 수신인을 더하고 평면 컬럼을 맞춘다', async () => {
  const out = await call({
    ...auth,
    action: 'add_receiver',
    receiver: { name: ' 이 ', value: ' a@b.co ', type: 'email' },
    telegram_bot_token: 'new-token',
  });
  assert.equal(out.status, 200);
  const { body } = writes()[0];
  assert.equal(body.telegram_chat_ids, '111');
  assert.equal(body.alert_emails, 'a@b.co');
  assert.equal(body.toc_alert_high.telegram_bot_token, 'new-token');
  assert.deepEqual(body.toc_alert_high.receivers.map((r) => r.value), ['111', 'a@b.co']);
  assert.equal(body.toc_alert_high.receivers[1].name, '이');
});

test('add_receiver 는 중복과 잘못된 값을 거부한다', async () => {
  const add = (receiver) => call({ ...auth, action: 'add_receiver', receiver });
  assert.equal((await add({ name: 'a', value: '111', type: 'telegram' })).status, 409);
  assert.equal((await add({ name: 'a', value: 'abc', type: 'telegram' })).status, 400);
  assert.equal((await add({ name: 'a', value: 'nope', type: 'email' })).status, 400);
  assert.equal((await add({ name: 'a', value: '1', type: 'sms' })).status, 400);
  assert.equal(writes().length, 0);
});

test('delete_receiver 는 지운 수신인을 돌려주고 나머지를 보존한다', async () => {
  const out = await call({ ...auth, action: 'delete_receiver', value: '111' });
  assert.equal(out.status, 200);
  assert.equal(out.json.removed.value, '111');
  const { body } = writes()[0];
  assert.deepEqual(body.toc_alert_high.receivers, []);
  assert.equal(body.telegram_chat_ids, '');
  assert.equal(body.toc_alert_high.telegram_bot_token, 'old-token');
});

test('insert_mock 은 표식을 강제하고 지점을 서버 값으로 쓴다', async () => {
  const out = await call({
    ...auth,
    action: 'insert_mock',
    channel: 3,
    toc: 12.5,
    date_time: '2026-11-05 13:30:00',
    use_device: true,
    Add_note: '가짜 아님',
    Site_ID: 'OTHER',
  });
  assert.equal(out.status, 200);
  const [post] = writes();
  assert.match(post.url, /\/rest\/v1\/measure_logs_v2$/);
  assert.equal(post.body.Add_note, '[MOCK TEST DATA]');
  assert.equal(post.body.Site_ID, 'SITE-1');
  assert.equal(post.body.Device_ID, 'DEV-1');
  assert.equal(post.body.Channel_Name, '방류수');
});

test('insert_mock 은 기기 지정이 없으면 모의 기기로 넣는다', async () => {
  const out = await call({ ...auth, action: 'insert_mock', channel: 4, toc: 0, date_time: '2026-11-05 13:30:00' });
  assert.equal(out.status, 200);
  const { body } = writes()[0];
  assert.equal(body.Device_ID, 'MOCK-DEVICE');
  assert.equal(body.Channel_Name, '채널 4');
});

test('insert_mock 은 잘못된 값을 거부한다', async () => {
  const base = { ...auth, action: 'insert_mock', channel: 1, toc: 1, date_time: '2026-11-05 13:30:00' };
  for (const bad of [{ channel: 0 }, { channel: 1.5 }, { toc: -1 }, { toc: 'x' }, { date_time: '2026-11-05T13:30:00Z' }]) {
    assert.equal((await call({ ...base, ...bad })).status, 400);
  }
  assert.equal(writes().length, 0);
});

test('delete_mock 은 항상 모의 데이터 표식으로만 지운다', async () => {
  assert.equal((await call({ ...auth, action: 'delete_mock' })).status, 200);
  assert.equal((await call({ ...auth, action: 'delete_mock', use_device: true })).status, 200);
  const [bySite, byDevice] = writes();
  assert.equal(bySite.method, 'DELETE');
  assert.match(bySite.url, /Add_note=eq\.%5BMOCK%20TEST%20DATA%5D&Site_ID=eq\.SITE-1$/);
  assert.match(byDevice.url, /Add_note=eq\.%5BMOCK%20TEST%20DATA%5D&Device_ID=eq\.DEV-1$/);
});

test('DB 오류 응답에 키나 내부 경로를 싣지 않는다', async () => {
  globalThis.fetch = async () => new Response('secret detail', { status: 500 });
  const out = await call({ ...auth, action: 'delete_mock' });
  assert.equal(out.status, 502);
  assert.doesNotMatch(JSON.stringify(out.json), /secret|test-service-key|rest\/v1/);
});

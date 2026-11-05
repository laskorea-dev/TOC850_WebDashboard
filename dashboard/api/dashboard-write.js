// 고객용 대시보드의 쓰기 전용 서버 API.
//
// 브라우저 번들에는 anon(조회 전용) 키만 싣고, 쓰기는 모두 이곳을 거친다.
// service_role 키는 서버 환경변수에만 둔다. VITE_ 접두사를 붙이면 번들에 그대로 들어가므로 금지.
//
// 요청마다 device_config 의 패스코드를 서버에서 대조하고, 아래 action 과 허용 필드만 처리한다.
// 임의 테이블·컬럼을 받는 범용 프록시로 만들지 말 것.

const MOCK_NOTE = '[MOCK TEST DATA]';
const MOCK_DEVICE = 'MOCK-DEVICE';
const DEFAULT_PASSCODE = '850'; // App.jsx 접속 화면의 폴백과 같아야 한다.
const CHANNEL_NAMES = { 1: '유입수', 2: '1차처리수', 3: '방류수', 5: 'test' };
const RECEIVER_TYPES = ['telegram', 'email'];
const MAX_TEXT = 500;

class HttpError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

const isText = (v, max = MAX_TEXT) => typeof v === 'string' && v.length <= max;

function parseBody(req) {
  if (req.body && typeof req.body === 'object') return req.body;
  if (typeof req.body === 'string') {
    try {
      return JSON.parse(req.body);
    } catch {
      throw new HttpError(400, '요청 형식이 올바르지 않습니다.');
    }
  }
  throw new HttpError(400, '요청 본문이 없습니다.');
}

function createDb() {
  const url = process.env.SUPABASE_URL;
  // 같은 프로젝트의 send-alert·telegram-webhook 과 같은 변수를 읽는다.
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_KEY;
  if (!url || !key) {
    console.error('dashboard-write: 서버용 SUPABASE_URL 또는 키 환경변수가 없습니다.');
    throw new HttpError(500, '서버 설정 오류입니다. 관리자에게 문의해 주세요.');
  }
  const base = `${url.replace(/\/+$/, '').replace(/\/rest\/v1$/, '')}/rest/v1`;

  return async function db(path, { method = 'GET', body, prefer } = {}) {
    const response = await fetch(`${base}/${path}`, {
      method,
      headers: {
        apikey: key,
        Authorization: `Bearer ${key}`,
        'Content-Type': 'application/json',
        ...(prefer ? { Prefer: prefer } : {}),
      },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
    if (!response.ok) {
      console.error(`dashboard-write: DB 요청 실패 ${method} ${path.split('?')[0]} ${response.status}`);
      throw new HttpError(502, '데이터베이스 요청에 실패했습니다.');
    }
    const text = await response.text();
    return text ? JSON.parse(text) : null;
  };
}

async function loadAuthorizedDevice(db, deviceId, passcode) {
  if (!isText(deviceId, 200) || !deviceId) throw new HttpError(400, '기기 정보가 없습니다.');
  if (!isText(passcode, 200)) throw new HttpError(401, '보안 코드가 올바르지 않습니다.');

  const rows = await db(`device_config?device_id=eq.${encodeURIComponent(deviceId)}&limit=1`);
  const row = Array.isArray(rows) ? rows[0] : null;
  // 기기 유무를 구분해 알려 주지 않는다.
  if (!row || passcode !== (row.passcode || DEFAULT_PASSCODE)) {
    throw new HttpError(401, '보안 코드가 올바르지 않습니다.');
  }
  return row;
}

function parseAlerts(raw) {
  if (!raw) return {};
  if (typeof raw === 'object') return raw;
  try {
    return JSON.parse(raw) || {};
  } catch {
    return {};
  }
}

function flattenReceivers(receivers) {
  const join = (type) => receivers.filter((r) => r.type === type).map((r) => r.value).join(',');
  return { telegram_chat_ids: join('telegram'), alert_emails: join('email') };
}

function patchDevice(db, deviceId, payload) {
  return db(`device_config?device_id=eq.${encodeURIComponent(deviceId)}`, {
    method: 'PATCH',
    body: payload,
    prefer: 'return=minimal',
  });
}

function withBotToken(alerts, token) {
  return isText(token, 200) ? { ...alerts, telegram_bot_token: token } : alerts;
}

const actions = {
  async save_config({ db, row, body }) {
    const { toc_alert_high, telegram_chat_ids, alert_emails, site_name, new_passcode } = body;
    if (!toc_alert_high || typeof toc_alert_high !== 'object' || Array.isArray(toc_alert_high)) {
      throw new HttpError(400, '임계값 설정 형식이 올바르지 않습니다.');
    }
    const texts = [telegram_chat_ids, alert_emails, site_name, new_passcode];
    if (!texts.every((v) => v === undefined || isText(v))) {
      throw new HttpError(400, '입력값이 너무 길거나 형식이 올바르지 않습니다.');
    }

    const payload = { toc_alert_high };
    if (telegram_chat_ids !== undefined) payload.telegram_chat_ids = telegram_chat_ids;
    if (alert_emails !== undefined) payload.alert_emails = alert_emails;
    if (site_name) payload.site_name = site_name;
    if (new_passcode) payload.passcode = new_passcode;

    await patchDevice(db, row.device_id, payload);
    return { ok: true };
  },

  async add_receiver({ db, row, body }) {
    const { receiver, telegram_bot_token } = body;
    const name = isText(receiver?.name, 100) ? receiver.name.trim() : '';
    const value = isText(receiver?.value, 200) ? receiver.value.trim() : '';
    const type = receiver?.type;
    if (!name || !value || !RECEIVER_TYPES.includes(type)) {
      throw new HttpError(400, '수신인 정보가 올바르지 않습니다.');
    }
    if (type === 'telegram' && !/^-?\d+$/.test(value)) {
      throw new HttpError(400, '텔레그램 Chat ID는 숫자로 입력해야 합니다.');
    }
    if (type === 'email' && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
      throw new HttpError(400, '올바른 이메일 형식이 아닙니다.');
    }

    const alerts = parseAlerts(row.toc_alert_high);
    const receivers = Array.isArray(alerts.receivers) ? alerts.receivers : [];
    if (receivers.some((r) => r.value === value)) {
      throw new HttpError(409, '이미 등록된 알림 수신처입니다.');
    }

    const updated = [...receivers, { name, value, type, created_at: new Date().toISOString() }];
    const flat = flattenReceivers(updated);
    await patchDevice(db, row.device_id, {
      toc_alert_high: withBotToken({ ...alerts, receivers: updated, ...flat }, telegram_bot_token),
      ...flat,
    });
    return { ok: true };
  },

  async delete_receiver({ db, row, body }) {
    const { value, telegram_bot_token } = body;
    if (!isText(value, 200) || !value) throw new HttpError(400, '수신인 정보가 올바르지 않습니다.');

    const alerts = parseAlerts(row.toc_alert_high);
    const receivers = Array.isArray(alerts.receivers) ? alerts.receivers : [];
    const removed = receivers.find((r) => r.value === value) || null;
    const updated = receivers.filter((r) => r.value !== value);
    const flat = flattenReceivers(updated);
    await patchDevice(db, row.device_id, {
      toc_alert_high: withBotToken({ ...alerts, receivers: updated, ...flat }, telegram_bot_token),
      ...flat,
    });
    return { ok: true, removed };
  },

  async insert_mock({ db, row, body, table }) {
    const channel = Number(body.channel);
    const toc = Number(body.toc);
    const { date_time, use_device } = body;
    if (!Number.isInteger(channel) || channel < 1 || channel > 8) {
      throw new HttpError(400, '채널 번호가 올바르지 않습니다.');
    }
    if (!Number.isFinite(toc) || toc < 0) throw new HttpError(400, '올바른 TOC 수치를 입력해주세요.');
    // 브라우저의 현지 시각을 그대로 받는다. 서버는 UTC 라 여기서 만들면 9시간 어긋난다.
    if (!isText(date_time, 19) || !/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(date_time)) {
      throw new HttpError(400, '측정 시각 형식이 올바르지 않습니다.');
    }

    await db(table, {
      method: 'POST',
      body: {
        Date_Time: date_time,
        Channel: channel,
        Channel_Name: CHANNEL_NAMES[channel] || `채널 ${channel}`,
        TOC_Conc: toc,
        DilutionFactor: 1.0,
        MSIG: 0.0,
        Add_note: MOCK_NOTE,
        Site_ID: row.site_id,
        Device_ID: use_device ? row.device_id : MOCK_DEVICE,
      },
      prefer: 'return=minimal',
    });
    return { ok: true };
  },

  async delete_mock({ db, row, body, table }) {
    // Add_note 조건은 항상 붙인다. 실제 측정 데이터가 지워지면 안 된다.
    const scope = body.use_device
      ? `Device_ID=eq.${encodeURIComponent(row.device_id)}`
      : `Site_ID=eq.${encodeURIComponent(row.site_id)}`;
    await db(`${table}?Add_note=eq.${encodeURIComponent(MOCK_NOTE)}&${scope}`, { method: 'DELETE' });
    return { ok: true };
  },
};

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method Not Allowed' });
  }

  try {
    const body = parseBody(req);
    const run = Object.hasOwn(actions, body.action) ? actions[body.action] : null;
    if (!run) throw new HttpError(400, '지원하지 않는 요청입니다.');

    const db = createDb();
    const row = await loadAuthorizedDevice(db, body.device_id, body.passcode);
    const table = process.env.SUPABASE_MEASUREMENT_TABLE || 'measure_logs_v2';
    const result = await run({ db, row, body, table });
    return res.status(200).json(result);
  } catch (err) {
    if (err instanceof HttpError) {
      return res.status(err.status).json({ error: err.message });
    }
    console.error('dashboard-write: 처리 중 오류', err);
    return res.status(500).json({ error: '서버 오류가 발생했습니다.' });
  }
}

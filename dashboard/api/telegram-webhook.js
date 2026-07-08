export default async function handler(req, res) {
  // POST 요청만 허용
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method Not Allowed' });
  }

  const { body } = req;
  if (!body || !body.message) {
    return res.status(200).json({ ok: true, message: 'No message' });
  }

  const { message } = body;
  const chat_id = message.chat?.id;
  const text = (message.text || '').trim();

  if (!chat_id || !text) {
    return res.status(200).json({ ok: true });
  }

  // Vercel 환경 변수에서 설정값 가져오기
  const botToken = process.env.TELEGRAM_BOT_TOKEN;
  const supabaseUrl = process.env.SUPABASE_URL;
  const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_KEY;

  if (!botToken || !supabaseUrl || !supabaseKey) {
    console.error('Vercel Config Error: Missing env variables.');
    return res.status(500).json({ error: 'Server configuration error' });
  }

  // 텔레그램 답장 전송 공통 함수
  const sendReply = async (replyText) => {
    try {
      await fetch(`https://api.telegram.org/bot${botToken}/sendMessage`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          chat_id: chat_id,
          text: replyText,
          parse_mode: 'HTML'
        })
      });
    } catch (e) {
      console.error('Telegram reply send error:', e);
    }
  };

  // "/등록" 또는 "/reg" 명령어 검출
  if (text.startsWith('/등록') || text.startsWith('/reg')) {
    const tokens = text.split(/\s+/);
    if (tokens.length < 4) {
      await sendReply(
        "⚠️ <b>사용법 오류</b>\n\n올바른 등록 포맷으로 메시지를 전송해 주세요.\n\n양식:\n<code>/등록 [디바이스ID] [사용자명] [패스코드]</code>\n예: <code>/등록 toc-260706-02 홍길동 850</code>"
      );
      return res.status(200).json({ ok: true });
    }

    const deviceId = tokens[1].trim();
    const username = tokens[2].trim();
    const inputPasscode = tokens[3].trim();

    try {
      let cleanUrl = supabaseUrl.replace(/\/+$/, '');
      if (cleanUrl.includes('/rest/v1')) {
        cleanUrl = cleanUrl.replace(/\/rest\/v1$/, '');
      }
      const queryUrl = `${cleanUrl}/rest/v1/device_config?device_id=eq.${encodeURIComponent(deviceId)}`;
      
      const response = await fetch(queryUrl, {
        method: 'GET',
        headers: {
          'apikey': supabaseKey,
          'Authorization': `Bearer ${supabaseKey}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        await sendReply("❌ <b>등록 실패</b>\n\n데이터베이스 연동 실패 (서버 연결 오류).");
        return res.status(200).json({ ok: true });
      }

      const deviceList = await response.json();
      if (!deviceList || deviceList.length === 0) {
        await sendReply(`❌ <b>등록 실패</b>\n\n존재하지 않는 디바이스 ID입니다: <code>{deviceId}</code>`);
        return res.status(200).json({ ok: true });
      }

      const deviceConf = deviceList[0];
      const dbPasscode = String(deviceConf.passcode || '').trim();

      if (inputPasscode !== dbPasscode) {
        await sendReply("❌ <b>등록 실패</b>\n\n보안 패스코드가 일치하지 않습니다.");
        return res.status(200).json({ ok: true });
      }

      let toc_alert_high = deviceConf.toc_alert_high || {};
      if (typeof toc_alert_high !== 'object') {
        toc_alert_high = {};
      }

      let receivers = toc_alert_high.receivers || [];
      if (!Array.isArray(receivers)) {
        receivers = [];
      }

      const exists = receivers.some(r => String(r.value) === String(chat_id));
      if (exists) {
        await sendReply(`ℹ️ <b>안내</b>\n\n이미 해당 디바이스(${deviceId})의 수신자로 등록되어 있습니다.`);
        return res.status(200).json({ ok: true });
      }

      receivers.push({
        name: username,
        type: 'telegram',
        value: String(chat_id)
      });
      toc_alert_high.receivers = receivers;

      // PATCH 로 Supabase 업데이트
      const updateUrl = `${cleanUrl}/rest/v1/device_config?device_id=eq.${encodeURIComponent(deviceId)}`;
      const updateRes = await fetch(updateUrl, {
        method: 'PATCH',
        headers: {
          'apikey': supabaseKey,
          'Authorization': `Bearer ${supabaseKey}`,
          'Content-Type': 'application/json',
          'Prefer': 'return=representation'
        },
        body: JSON.stringify({ toc_alert_high })
      });

      if (updateRes.ok) {
        await sendReply(
          `🎉 <b>TOC 경보 알림 수신 등록 완료</b>\n\n안녕하세요, <b>${username}</b>님!\n디바이스 <b>${deviceId}</b>의 실시간 알림 수신처로 정상 등록되었습니다.\n\n앞으로 경보 발생 시 본 대화방으로 알림이 전송됩니다.`
        );
      } else {
        await sendReply("❌ <b>등록 실패</b>\n\n데이터베이스 업데이트에 실패했습니다.");
      }
    } catch (err) {
      console.error(err);
      await sendReply("❌ <b>등록 실패</b>\n\n서버 처리 중 알 수 없는 예외가 발생했습니다.");
    }
  }

  return res.status(200).json({ ok: true });
}

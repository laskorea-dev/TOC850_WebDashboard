export default async function handler(req, res) {
  // POST 요청만 허용
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method Not Allowed' });
  }

  const { body } = req;
  if (!body || !body.record) {
    return res.status(200).json({ ok: true, message: 'No record in body' });
  }

  const record = body.record;
  const deviceId = (record.Device_ID || record.device_id || '').trim().toUpperCase();
  const channelId = String(record.Channel || record.channel || '');
  const tocVal = parseFloat(record.TOC_Conc || record.toc_conc || 0.0);
  const dateTime = record.Date_Time || record.date_time || new Date().toLocaleString();

  if (!deviceId || !channelId) {
    return res.status(200).json({ ok: true, message: 'Missing Device_ID or Channel' });
  }

  const supabaseUrl = process.env.SUPABASE_URL;
  const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_KEY;
  const botToken = process.env.TELEGRAM_BOT_TOKEN || '<TELEGRAM_BOT_TOKEN>';

  if (!supabaseUrl || !supabaseKey || !botToken) {
    console.error('Serverless Config Error: Missing env variables.');
    return res.status(500).json({ error: 'Server configuration error' });
  }

  try {
    // 1. Supabase에서 해당 디바이스의 설정 조회
    const cleanUrl = supabaseUrl.replace(/\/+$/, '').replace(/\/rest\/v1$/, '');
    const queryUrl = `${cleanUrl}/rest/v1/device_config?device_id=eq.${encodeURIComponent(deviceId)}`;
    
    const dbResponse = await fetch(queryUrl, {
      method: 'GET',
      headers: {
        'apikey': supabaseKey,
        'Authorization': `Bearer ${supabaseKey}`,
        'Content-Type': 'application/json'
      }
    });

    if (!dbResponse.ok) {
      return res.status(500).json({ error: 'DB Query Failed' });
    }

    const deviceList = await dbResponse.json();
    if (!deviceList || deviceList.length === 0) {
      return res.status(200).json({ ok: true, message: `Device ID ${deviceId} is not registered` });
    }

    const deviceConf = deviceList[0];
    const siteName = deviceConf.site_name || deviceId;
    let toc_alert_high = deviceConf.toc_alert_high || {};
    if (typeof toc_alert_high !== 'object') {
      toc_alert_high = {};
    }

    // 2. 채널 기본 임계치 설정 (업로더와 연동 통일)
    let warningLimit = 6000.0;
    let cautionLimit = 4500.0;
    let alertLevel = 'warning'; // 'warning' 또는 'caution'

    if (channelId === '3') { // 방류수
      cautionLimit = 35.0;
      warningLimit = 50.0;
    } else if (channelId === '2') { // 1차처리수
      cautionLimit = 800.0;
      warningLimit = 1000.0;
    } else if (channelId === '1') { // 유입수
      cautionLimit = 1500.0;
      warningLimit = 2000.0;
    }

    // DB 개별 임계값 적용
    const chConfig = toc_alert_high[channelId];
    if (chConfig && typeof chConfig === 'object') {
      warningLimit = parseFloat(chConfig.warning || warningLimit);
      cautionLimit = parseFloat(chConfig.caution || cautionLimit);
      alertLevel = chConfig.alert_level || 'warning';
    }

    // 알림 유형 기준 한도값 결정
    const triggerLimit = alertLevel === 'caution' ? cautionLimit : warningLimit;
    const alertTypeStr = alertLevel === 'caution' ? '주의' : '경고';

    // 3. 수치 초과 여부 감사
    if (tocVal < triggerLimit) {
      return res.status(200).json({ ok: true, message: 'Normal value' });
    }

    // 4. 1시간 발송 쿨다운 검사
    let lastAlertTimeMap = toc_alert_high.last_alert_time || {};
    const lastAlertTimeStr = lastAlertTimeMap[channelId];
    const now = new Date();

    if (lastAlertTimeStr) {
      const lastAlertTime = new Date(lastAlertTimeStr);
      const diffSeconds = (now.getTime() - lastAlertTime.getTime()) / 1000;
      if (diffSeconds < 3600) {
        return res.status(200).json({ ok: true, message: `Cooldown active. ${Math.round(3600 - diffSeconds)}s left.` });
      }
    }

    // 5. 알림 대상자 파싱
    const receivers = toc_alert_high.receivers || [];
    const telegramChatIds = receivers
      .filter(r => r.type === 'telegram' && r.value)
      .map(r => String(r.value));

    if (telegramChatIds.length === 0) {
      return res.status(200).json({ ok: true, message: 'No registered telegram receivers' });
    }

    // 6. 텔레그램 알림 발송
    const messageText = 
      `🚨 <b>TOC 수치 초과 [${alertTypeStr} 알림]</b>\n\n` +
      `🏢 <b>지점명</b>: ${siteName}\n` +
      `🌊 <b>채널명</b>: Ch ${channelId}\n` +
      `🕒 <b>측정시간</b>: ${dateTime}\n` +
      `📉 <b>설정 임계값</b>: ${triggerLimit} ppm\n` +
      `⚠️ <b>현재 측정값</b>: <font color="red"><b>${tocVal} ppm</b></font>\n\n` +
      `<i>※ 수치 초과 상태이오니 현장 장비 및 대시보드를 확인하시기 바랍니다.</i>`;

    let tgSent = false;
    for (const chatId of telegramChatIds) {
      try {
        await fetch(`https://api.telegram.org/bot${botToken}/sendMessage`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            chat_id: chatId,
            text: messageText,
            parse_mode: 'HTML'
          })
        });
        tgSent = true;
      } catch (e) {
        console.error(`Telegram alert send error for chat_id ${chatId}:`, e);
      }
    }

    // 7. 발송이 한 번이라도 일어났다면 쿨다운 기록 저장
    if (tgSent) {
      lastAlertTimeMap[channelId] = now.toISOString();
      toc_alert_high.last_alert_time = lastAlertTimeMap;

      const updateUrl = `${cleanUrl}/rest/v1/device_config?device_id=eq.${encodeURIComponent(deviceId)}`;
      await fetch(updateUrl, {
        method: 'PATCH',
        headers: {
          'apikey': supabaseKey,
          'Authorization': `Bearer ${supabaseKey}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ toc_alert_high })
      });
    }

    return res.status(200).json({ ok: true, telegram: tgSent });

  } catch (err) {
    console.error('Serverless alert trigger processing error:', err);
    return res.status(500).json({ error: 'Internal server error' });
  }
}

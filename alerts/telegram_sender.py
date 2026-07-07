import urllib.request
import urllib.parse
import json
import re
from alerts.base import BaseAlertSender

class TelegramAlertSender(BaseAlertSender):
    def __init__(self, bot_token: str, log_queue=None):
        self.bot_token = bot_token
        self.log_queue = log_queue

    def _format_html_for_telegram(self, html_body: str) -> str:
        """HTML body에서 스타일, 헤더 태그를 지우고 텔레그램에서 지원하는 태그(<b>, <i>, <a> 등)만 남겨 반환합니다."""
        if not html_body:
            return ""
            
        # 1. <style> 및 <head> 영역 제거
        html = re.sub(r'<(style|head|script)[^>]*>.*?</\1>', '', html_body, flags=re.DOTALL | re.IGNORECASE)
        
        # 2. 줄바꿈 보정을 위해 주요 블록 태그 변환
        html = re.sub(r'<tr[^>]*>', '\n', html, flags=re.IGNORECASE)
        html = re.sub(r'<td[^>]*>', '  ', html, flags=re.IGNORECASE)
        html = re.sub(r'</(td|tr|p|div|h1|h2|h3|h4|h5|h6|li)>', '\n', html, flags=re.IGNORECASE)
        html = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
        
        # 3. 텔레그램에서 지원하는 HTML 태그 목록
        allowed_tags = ['b', 'strong', 'i', 'em', 'u', 'ins', 's', 'strike', 'del', 'a', 'code', 'pre']
        
        # 4. 허용되지 않은 태그 모두 제거
        def tag_repl(match):
            full_tag = match.group(0)
            inner = match.group(1)
            # 태그명 추출 (예: 'a href="..."' -> 'a')
            tag_name = inner.split()[0].lower()
            if tag_name.startswith('/'):
                tag_name = tag_name[1:]
            
            if tag_name in allowed_tags:
                return full_tag
            return ""
            
        html = re.sub(r'<(/?[a-zA-Z0-9]+(?:\s+[^>]*)?)>', tag_repl, html)
        
        # 5. 연속된 줄바꿈 정리
        html = re.sub(r'\n\s*\n+', '\n\n', html)
        return html.strip()

    def send_alert(self, recipients: str, subject: str, body: str) -> bool:
        """텔레그램 봇을 통해 다중 Chat ID 또는 단톡방 ID로 메시지를 전송합니다.
        
        Args:
            recipients: 쉼표(,)로 구분된 Telegram Chat ID 목록 (예: "12345678,-100987654321")
            subject: 알람 제목
            body: 알람 본문 (HTML 형식 또는 텍스트)
            
        Returns:
            bool: 발송 성공 여부 (모든 대상 전송 실패 시 False)
        """
        if not self.bot_token:
            self._log("[텔레그램 알람 실패] Bot Token이 설정되어 있지 않습니다.")
            return False
            
        chat_ids = [cid.strip() for cid in recipients.split(",") if cid.strip()]
        if not chat_ids:
            self._log("[텔레그램 알람 실패] 수신 대상 Chat ID가 없습니다.")
            return False
            
        # 텔레그램 메시지 포맷팅
        formatted_body = self._format_html_for_telegram(body)
        message = f"🚨 <b>{subject}</b>\n\n{formatted_body}"
        
        success_count = 0
        for chat_id in chat_ids:
            try:
                url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
                payload = {
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "HTML"
                }
                data_bytes = json.dumps(payload).encode('utf-8')
                
                req = urllib.request.Request(
                    url,
                    data=data_bytes,
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                
                with urllib.request.urlopen(req, timeout=5) as response:
                    if response.status in [200, 201]:
                        self._log(f"[텔레그램 발송 성공] Chat ID: {chat_id}")
                        success_count += 1
                    else:
                        self._log(f"[텔레그램 발송 실패] Chat ID {chat_id}: HTTP {response.status}")
            except Exception as e:
                self._log(f"[텔레그램 발송 오류] Chat ID {chat_id}: {e}")
                
        return success_count > 0

    def _log(self, text: str):
        if self.log_queue:
            self.log_queue.put(("log", text))
        else:
            print(text)

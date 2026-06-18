import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from alerts.base import BaseAlertSender

class EmailAlertSender(BaseAlertSender):
    def __init__(self, smtp_server, smtp_port, smtp_user, smtp_password, smtp_use_tls=True, log_queue=None):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.smtp_use_tls = smtp_use_tls
        self.log_queue = log_queue

    def log(self, message):
        if self.log_queue:
            self.log_queue.put(("log", message))
        else:
            print(message)

    def send_alert(self, recipients: str, subject: str, body: str) -> bool:
        if not recipients:
            self.log("[메일 발송 스킵] 수신인 주소가 없습니다.")
            return False
        
        if not self.smtp_server or not self.smtp_user or not self.smtp_password:
            self.log("[메일 발송 실패] SMTP 설정이 올바르지 않습니다.")
            return False

        try:
            # 이메일 메시지 구성
            msg = MIMEMultipart()
            msg["From"] = self.smtp_user
            msg["To"] = recipients
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "html", "utf-8"))

            # SMTP 서버 연결
            server = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=10)
            if self.smtp_use_tls:
                server.starttls()
            
            server.login(self.smtp_user, self.smtp_password)
            
            # 수신인 주소 분리 (쉼표 구분 대응)
            recipient_list = [r.strip() for r in recipients.split(",") if r.strip()]
            
            server.sendmail(self.smtp_user, recipient_list, msg.as_string())
            server.quit()
            
            self.log(f"[메일 발송 성공] 수신자: {recipients}")
            return True
        except Exception as e:
            self.log(f"[메일 발송 실패] 오류: {e}")
            return False

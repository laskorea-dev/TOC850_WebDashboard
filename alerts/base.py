from abc import ABC, abstractmethod

class BaseAlertSender(ABC):
    @abstractmethod
    def send_alert(self, recipients: str, subject: str, body: str) -> bool:
        """알람을 발송합니다.
        
        Args:
            recipients: 수신인 정보 (이메일 주소, 전화번호 등, 여러 명일 경우 콤마 구분)
            subject: 알람 제목
            body: 알람 본문 (HTML 또는 plain text)
            
        Returns:
            bool: 발송 성공 여부
        """
        pass

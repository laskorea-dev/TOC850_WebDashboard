from alerts.base import BaseAlertSender
from alerts.email_sender import EmailAlertSender

def get_alert_sender(alert_type: str, **kwargs) -> BaseAlertSender:
    """설정된 alert_type에 부합하는 알림 발송 객체를 생성하여 반환합니다.
    지원하지 않는 타입이 지정될 경우, 기본적으로 EmailAlertSender로 폴백합니다.
    """
    normalized_type = str(alert_type).strip().lower()
    
    if normalized_type == "email" or not normalized_type:
        return EmailAlertSender(
            smtp_server=kwargs.get("smtp_server", ""),
            smtp_port=kwargs.get("smtp_port", 587),
            smtp_user=kwargs.get("smtp_user", ""),
            smtp_password=kwargs.get("smtp_password", ""),
            smtp_use_tls=kwargs.get("smtp_use_tls", True),
            log_queue=kwargs.get("log_queue")
        )
    # elif normalized_type == "kakao":
    #     return KakaoAlertSender(...)
    else:
        # 미지원 타입에 대해 일단 EmailAlertSender로 안전하게 폴백 처리합니다.
        # 향후 다른 모듈 연동 전까지 유연성 확보
        return EmailAlertSender(
            smtp_server=kwargs.get("smtp_server", ""),
            smtp_port=kwargs.get("smtp_port", 587),
            smtp_user=kwargs.get("smtp_user", ""),
            smtp_password=kwargs.get("smtp_password", ""),
            smtp_use_tls=kwargs.get("smtp_use_tls", True),
            log_queue=kwargs.get("log_queue")
        )

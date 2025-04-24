import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Optional
import requests
from datetime import datetime

logger = logging.getLogger(__name__)

class AlertSender:
    def __init__(self):
        # 이메일 설정
        self.smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_user = os.getenv('SMTP_USER')
        self.smtp_password = os.getenv('SMTP_PASSWORD')
        self.smtp_from = os.getenv('SMTP_FROM')
        self.smtp_to = os.getenv('SMTP_TO')
        
        # Slack 설정
        self.slack_webhook_url = os.getenv('SLACK_WEBHOOK_URL')
        self.slack_channel = os.getenv('SLACK_CHANNEL', '#monitoring')
        
        # 알림 템플릿
        self.templates = {
            'service_down': {
                'email': {
                    'subject': '[경고] 서비스 다운',
                    'body': '''
                    서비스 상태 경고
                    
                    서비스: {service_name}
                    상태: 다운
                    시간: {timestamp}
                    상세: {details}
                    '''
                },
                'slack': {
                    'color': '#FF0000',
                    'title': '서비스 다운 경고',
                    'text': '''
                    *서비스*: {service_name}
                    *상태*: 다운
                    *시간*: {timestamp}
                    *상세*: {details}
                    '''
                }
            },
            'high_resource': {
                'email': {
                    'subject': '[경고] 리소스 사용량 초과',
                    'body': '''
                    리소스 사용량 경고
                    
                    리소스: {resource_type}
                    사용량: {usage}%
                    임계값: {threshold}%
                    시간: {timestamp}
                    '''
                },
                'slack': {
                    'color': '#FFA500',
                    'title': '리소스 사용량 경고',
                    'text': '''
                    *리소스*: {resource_type}
                    *사용량*: {usage}%
                    *임계값*: {threshold}%
                    *시간*: {timestamp}
                    '''
                }
            }
        }

    def send_email(self, template: str, data: Dict) -> bool:
        """이메일 알림 전송"""
        if not all([self.smtp_user, self.smtp_password, self.smtp_from, self.smtp_to]):
            logger.error("이메일 설정이 불완전합니다.")
            return False

        try:
            msg = MIMEMultipart()
            msg['From'] = self.smtp_from
            msg['To'] = self.smtp_to
            msg['Subject'] = self.templates[template]['email']['subject']

            body = self.templates[template]['email']['body'].format(
                timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                **data
            )
            msg.attach(MIMEText(body, 'plain'))

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            logger.info(f"이메일 알림 전송 성공: {template}")
            return True
        except Exception as e:
            logger.error(f"이메일 알림 전송 실패: {str(e)}")
            return False

    def send_slack(self, template: str, data: Dict) -> bool:
        """Slack 알림 전송"""
        if not self.slack_webhook_url:
            logger.error("Slack 웹훅 URL이 설정되지 않았습니다.")
            return False

        try:
            template_data = self.templates[template]['slack']
            message = {
                'channel': self.slack_channel,
                'attachments': [{
                    'color': template_data['color'],
                    'title': template_data['title'],
                    'text': template_data['text'].format(
                        timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        **data
                    ),
                    'footer': '모니터링 서비스',
                    'ts': datetime.now().timestamp()
                }]
            }

            response = requests.post(
                self.slack_webhook_url,
                json=message,
                headers={'Content-Type': 'application/json'}
            )
            response.raise_for_status()

            logger.info(f"Slack 알림 전송 성공: {template}")
            return True
        except Exception as e:
            logger.error(f"Slack 알림 전송 실패: {str(e)}")
            return False

    def send_alert(self, alert_type: str, data: Dict) -> None:
        """알림 전송 (이메일 및 Slack)"""
        if alert_type not in self.templates:
            logger.error(f"알 수 없는 알림 유형: {alert_type}")
            return

        email_sent = self.send_email(alert_type, data)
        slack_sent = self.send_slack(alert_type, data)

        if not email_sent and not slack_sent:
            logger.error("모든 알림 전송이 실패했습니다.")

    def send_service_down_alert(self, service_name: str, details: str) -> None:
        """서비스 다운 알림 전송"""
        self.send_alert('service_down', {
            'service_name': service_name,
            'details': details
        })

    def send_resource_alert(self, resource_type: str, usage: float, threshold: float) -> None:
        """리소스 사용량 알림 전송"""
        self.send_alert('high_resource', {
            'resource_type': resource_type,
            'usage': usage,
            'threshold': threshold
        }) 
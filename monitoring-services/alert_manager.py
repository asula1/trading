import os
import time
import logging
import smtplib
import json
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from dotenv import load_dotenv
from prometheus_client import Gauge
import psutil

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.config.fileConfig('logging.conf')
logger = logging.getLogger('monitoring')

# 알림 상태 메트릭
ALERT_STATUS = Gauge('alert_status', '알림 상태', ['alert_type', 'service'])

class AlertManager:
    def __init__(self):
        self.alert_history = {}
        self.thresholds = {
            'cpu': float(os.getenv('CPU_ALERT_THRESHOLD', 80)),
            'memory': float(os.getenv('MEMORY_ALERT_THRESHOLD', 85)),
            'disk': float(os.getenv('DISK_ALERT_THRESHOLD', 90))
        }
        
        # 이메일 설정
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', 587))
        self.smtp_username = os.getenv('SMTP_USERNAME')
        self.smtp_password = os.getenv('SMTP_PASSWORD')
        self.alert_email = os.getenv('ALERT_EMAIL')
        
        # Slack 설정
        self.slack_webhook = os.getenv('SLACK_WEBHOOK_URL')
        
        logger.info("알림 관리자 초기화 완료")

    def check_thresholds(self, metrics):
        """메트릭 임계값 확인 및 알림 발송"""
        alerts = []
        
        # CPU 사용량 확인
        if metrics['cpu'] > self.thresholds['cpu']:
            alerts.append({
                'type': 'cpu',
                'value': metrics['cpu'],
                'threshold': self.thresholds['cpu'],
                'message': f'CPU 사용량이 {metrics["cpu"]}%로 임계값 {self.thresholds["cpu"]}%를 초과했습니다.'
            })
        
        # 메모리 사용량 확인
        if metrics['memory'] > self.thresholds['memory']:
            alerts.append({
                'type': 'memory',
                'value': metrics['memory'],
                'threshold': self.thresholds['memory'],
                'message': f'메모리 사용량이 {metrics["memory"]}%로 임계값 {self.thresholds["memory"]}%를 초과했습니다.'
            })
        
        # 디스크 사용량 확인
        if metrics['disk'] > self.thresholds['disk']:
            alerts.append({
                'type': 'disk',
                'value': metrics['disk'],
                'threshold': self.thresholds['disk'],
                'message': f'디스크 사용량이 {metrics["disk"]}%로 임계값 {self.thresholds["disk"]}%를 초과했습니다.'
            })
        
        return alerts

    def send_email_alert(self, alert):
        """이메일 알림 전송"""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.smtp_username
            msg['To'] = self.alert_email
            msg['Subject'] = f'[경고] {alert["type"].upper()} 사용량 초과'
            
 
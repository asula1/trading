import os
import time
import logging
import smtplib
import requests
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from .database import get_db
from .models import AlertConfig, AlertHistory
from .schemas import AlertConfigCreate, AlertHistoryCreate
from .alert_sender import AlertSender

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AlertManager:
    """알림 관리자"""
    
    def __init__(self, cooldown_period: int = 300):
        self.cooldown_period = cooldown_period
        self.last_alert_time = {}
        
        # 이메일 설정
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", 587))
        self.smtp_user = os.getenv("SMTP_USER", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.smtp_from = os.getenv("SMTP_FROM", "")
        
        # Slack 설정
        self.slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL", "")
        self.slack_channel = os.getenv("SLACK_CHANNEL", "#alerts")
        
        # 알림 설정
        self.alert_sender = AlertSender()
        self.alert_history: Dict[str, datetime] = {}
        
        # 기본 임계값 설정
        self.default_thresholds = {
            "cpu_usage": 80.0,
            "memory_usage": 85.0,
            "disk_usage": 90.0,
            "network_in": 1000000000,  # 1GB
            "network_out": 1000000000  # 1GB
        }
    
    def check_metrics(self, metrics: Dict[str, float]):
        """시스템 메트릭 체크 및 알림 발송"""
        try:
            # 현재 알림 설정 조회
            alert_config = self._get_alert_config()
            if not alert_config:
                alert_config = self._create_default_config()
            
            # 각 메트릭 체크
            alerts = []
            
            # CPU 사용량 체크
            if metrics["cpu_usage"] > alert_config.cpu_threshold:
                alerts.append({
                    "type": "cpu_usage",
                    "value": metrics["cpu_usage"],
                    "threshold": alert_config.cpu_threshold
                })
            
            # 메모리 사용량 체크
            if metrics["memory_usage"] > alert_config.memory_threshold:
                alerts.append({
                    "type": "memory_usage",
                    "value": metrics["memory_usage"],
                    "threshold": alert_config.memory_threshold
                })
            
            # 디스크 사용량 체크
            if metrics["disk_usage"] > alert_config.disk_threshold:
                alerts.append({
                    "type": "disk_usage",
                    "value": metrics["disk_usage"],
                    "threshold": alert_config.disk_threshold
                })
            
            # 네트워크 트래픽 체크
            if metrics["network_in"] > alert_config.network_in_threshold:
                alerts.append({
                    "type": "network_in",
                    "value": metrics["network_in"],
                    "threshold": alert_config.network_in_threshold
                })
            
            if metrics["network_out"] > alert_config.network_out_threshold:
                alerts.append({
                    "type": "network_out",
                    "value": metrics["network_out"],
                    "threshold": alert_config.network_out_threshold
                })
            
            # 알림 발송
            for alert in alerts:
                self._send_alert(alert)
                
        except Exception as e:
            logger.error(f"메트릭 체크 중 오류 발생: {e}")
    
    def check_service_status(self, service_name: str, is_healthy: bool):
        """서비스 상태 체크 및 알림 발송"""
        try:
            if not is_healthy:
                alert = {
                    "type": "service_down",
                    "service_name": service_name
                }
                self._send_alert(alert)
        except Exception as e:
            logger.error(f"서비스 상태 체크 중 오류 발생: {e}")
    
    def _send_alert(self, alert: Dict):
        """알림 발송"""
        try:
            # 알림 타입과 서비스 이름으로 키 생성
            alert_key = f"{alert['type']}_{alert.get('service_name', '')}"
            
            # 쿨다운 기간 체크
            if alert_key in self.last_alert_time:
                last_alert_time = self.last_alert_time[alert_key]
                if time.time() - last_alert_time < self.cooldown_period:
                    return
            
            # 알림 발송
            if alert["type"] == "service_down":
                self.alert_sender.send_service_down_alert(alert["service_name"])
            else:
                self.alert_sender.send_resource_alert(
                    alert["type"],
                    alert["value"],
                    alert["threshold"]
                )
            
            # 알림 이력 저장
            self._save_alert_history(alert)
            
            # 알림 시간 업데이트
            self.last_alert_time[alert_key] = time.time()
            
        except Exception as e:
            logger.error(f"알림 발송 중 오류 발생: {e}")
    
    def _get_alert_config(self) -> Optional[AlertConfig]:
        """알림 설정 조회"""
        try:
            db = next(get_db())
            return db.query(AlertConfig).first()
        except Exception as e:
            logger.error(f"알림 설정 조회 중 오류 발생: {e}")
            return None
        finally:
            if db:
                db.close()
    
    def _create_default_config(self) -> AlertConfig:
        """기본 알림 설정 생성"""
        try:
            db = next(get_db())
            config = AlertConfig(
                cpu_threshold=self.default_thresholds["cpu_usage"],
                memory_threshold=self.default_thresholds["memory_usage"],
                disk_threshold=self.default_thresholds["disk_usage"],
                network_in_threshold=self.default_thresholds["network_in"],
                network_out_threshold=self.default_thresholds["network_out"]
            )
            db.add(config)
            db.commit()
            return config
        except Exception as e:
            logger.error(f"기본 알림 설정 생성 중 오류 발생: {e}")
            if db:
                db.rollback()
            raise
        finally:
            if db:
                db.close()
    
    def _save_alert_history(self, alert: Dict):
        """알림 이력 저장"""
        try:
            db = next(get_db())
            history = AlertHistory(
                alert_type=alert["type"],
                service_name=alert.get("service_name", ""),
                value=alert.get("value", 0.0),
                threshold=alert.get("threshold", 0.0)
            )
            db.add(history)
            db.commit()
        except Exception as e:
            logger.error(f"알림 이력 저장 중 오류 발생: {e}")
            if db:
                db.rollback()
        finally:
            if db:
                db.close()
    
    def update_alert_config(self, config: AlertConfigCreate) -> AlertConfig:
        """알림 설정 업데이트"""
        try:
            db = next(get_db())
            current_config = db.query(AlertConfig).first()
            
            if current_config:
                current_config.cpu_threshold = config.cpu_threshold
                current_config.memory_threshold = config.memory_threshold
                current_config.disk_threshold = config.disk_threshold
                current_config.network_in_threshold = config.network_in_threshold
                current_config.network_out_threshold = config.network_out_threshold
            else:
                current_config = AlertConfig(**config.dict())
                db.add(current_config)
            
            db.commit()
            return current_config
        except Exception as e:
            logger.error(f"알림 설정 업데이트 중 오류 발생: {e}")
            if db:
                db.rollback()
            raise
        finally:
            if db:
                db.close()
    
    def get_alert_history(self, alert_type: Optional[str] = None) -> List[AlertHistory]:
        """알림 이력 조회"""
        try:
            db = next(get_db())
            query = db.query(AlertHistory)
            
            if alert_type:
                query = query.filter(AlertHistory.alert_type == alert_type)
            
            return query.order_by(AlertHistory.created_at.desc()).all()
        except Exception as e:
            logger.error(f"알림 이력 조회 중 오류 발생: {e}")
            return []
        finally:
            if db:
                db.close()
    
    def send_alert(self, alert_type: str, severity: str, message: str):
        """알림 전송"""
        try:
            # 쿨다운 체크
            if not self._check_cooldown(alert_type):
                logger.info(f"알림 {alert_type}는 쿨다운 기간 중입니다.")
                return
                
            # 알림 설정 조회
            alert_config = self._get_alert_config()
            if not alert_config:
                logger.warning(f"알림 {alert_type}에 대한 설정이 없습니다.")
                return
                
            # 알림 수신자 확인
            if not alert_config.enabled:
                logger.info(f"알림 {alert_type}는 비활성화되어 있습니다.")
                return
                
            # 알림 전송
            if alert_config.email_enabled:
                self._send_email_alert(alert_type, severity, message, alert_config.email_recipients)
                
            if alert_config.slack_enabled:
                self._send_slack_alert(alert_type, severity, message)
                
            # 알림 이력 저장
            self._save_alert_history(alert_type, severity, message)
            
            # 쿨다운 시간 업데이트
            self.last_alert_time[alert_type] = time.time()
            
        except Exception as e:
            logger.error(f"알림 전송 중 오류 발생: {str(e)}")
            
    def _check_cooldown(self, alert_type: str) -> bool:
        """쿨다운 기간 체크"""
        if alert_type not in self.last_alert_time:
            return True
            
        elapsed_time = time.time() - self.last_alert_time[alert_type]
        return elapsed_time >= self.cooldown_period
        
    def _send_email_alert(self, alert_type: str, severity: str, message: str, recipients: list):
        """이메일 알림 전송"""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.smtp_from
            msg['To'] = ', '.join(recipients)
            msg['Subject'] = f"[{severity.upper()}] {alert_type} 알림"
            
            body = f"""
            알림 유형: {alert_type}
            심각도: {severity}
            메시지: {message}
            시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
                
            logger.info(f"이메일 알림 전송 완료: {alert_type}")
            
        except Exception as e:
            logger.error(f"이메일 알림 전송 중 오류 발생: {str(e)}")
            
    def _send_slack_alert(self, alert_type: str, severity: str, message: str):
        """Slack 알림 전송"""
        try:
            if not self.slack_webhook_url:
                logger.warning("Slack 웹훅 URL이 설정되지 않았습니다.")
                return
                
            payload = {
                "channel": self.slack_channel,
                "text": f"""
                *[{severity.upper()}] {alert_type} 알림*
                > {message}
                > 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                """
            }
            
            response = requests.post(
                self.slack_webhook_url,
                json=payload,
                timeout=5
            )
            response.raise_for_status()
            
            logger.info(f"Slack 알림 전송 완료: {alert_type}")
            
        except Exception as e:
            logger.error(f"Slack 알림 전송 중 오류 발생: {str(e)}")
            
    def _save_alert_history(self, alert_type: str, severity: str, message: str):
        """알림 이력 저장"""
        try:
            db = next(get_db())
            history = AlertHistory(
                alert_type=alert_type,
                severity=severity,
                message=message,
                timestamp=datetime.now()
            )
            db.add(history)
            db.commit()
        except Exception as e:
            logger.error(f"알림 이력 저장 중 오류 발생: {e}")
            if db:
                db.rollback()
        finally:
            if db:
                db.close() 
import os
import sys
import time
import logging
import requests
from typing import Dict, List, Optional
from datetime import datetime, timedelta

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('health_check.log')
    ]
)
logger = logging.getLogger(__name__)

class HealthCheck:
    def __init__(self):
        self.api_url = os.getenv('API_URL', 'http://localhost:8000')
        self.consul_url = os.getenv('CONSUL_URL', 'http://localhost:8500')
        self.prometheus_url = os.getenv('PROMETHEUS_URL', 'http://localhost:9090')
        self.alertmanager_url = os.getenv('ALERTMANAGER_URL', 'http://localhost:9093')
        self.grafana_url = os.getenv('GRAFANA_URL', 'http://localhost:3000')
        
        self.check_interval = int(os.getenv('CHECK_INTERVAL', '60'))
        self.retry_count = int(os.getenv('RETRY_COUNT', '3'))
        self.retry_delay = int(os.getenv('RETRY_DELAY', '5'))
        
        self.failure_threshold = int(os.getenv('FAILURE_THRESHOLD', '3'))
        self.failure_window = int(os.getenv('FAILURE_WINDOW', '300'))
        
        self.failure_history: Dict[str, List[datetime]] = {}

    def check_api(self) -> bool:
        """API 서비스 상태 확인"""
        try:
            response = requests.get(f"{self.api_url}/")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"API 체크 실패: {str(e)}")
            return False

    def check_consul(self) -> bool:
        """Consul 서비스 상태 확인"""
        try:
            response = requests.get(f"{self.consul_url}/v1/status/leader")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Consul 체크 실패: {str(e)}")
            return False

    def check_prometheus(self) -> bool:
        """Prometheus 서비스 상태 확인"""
        try:
            response = requests.get(f"{self.prometheus_url}/-/healthy")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Prometheus 체크 실패: {str(e)}")
            return False

    def check_alertmanager(self) -> bool:
        """Alertmanager 서비스 상태 확인"""
        try:
            response = requests.get(f"{self.alertmanager_url}/-/healthy")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Alertmanager 체크 실패: {str(e)}")
            return False

    def check_grafana(self) -> bool:
        """Grafana 서비스 상태 확인"""
        try:
            response = requests.get(f"{self.grafana_url}/api/health")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Grafana 체크 실패: {str(e)}")
            return False

    def record_failure(self, service: str) -> None:
        """서비스 실패 기록"""
        now = datetime.now()
        if service not in self.failure_history:
            self.failure_history[service] = []
        
        self.failure_history[service].append(now)
        
        # 오래된 실패 기록 제거
        cutoff = now - timedelta(seconds=self.failure_window)
        self.failure_history[service] = [
            t for t in self.failure_history[service] if t > cutoff
        ]

    def should_alert(self, service: str) -> bool:
        """알림 전송 여부 확인"""
        if service not in self.failure_history:
            return False
        
        failures = self.failure_history[service]
        if len(failures) >= self.failure_threshold:
            return True
        
        return False

    def send_alert(self, service: str, status: bool) -> None:
        """알림 전송"""
        if not status:
            self.record_failure(service)
            if self.should_alert(service):
                logger.warning(f"서비스 {service}에 대한 알림 전송")
                # TODO: 실제 알림 전송 로직 구현
        else:
            if service in self.failure_history:
                del self.failure_history[service]

    def check_all_services(self) -> None:
        """모든 서비스 상태 확인"""
        services = {
            'api': self.check_api,
            'consul': self.check_consul,
            'prometheus': self.check_prometheus,
            'alertmanager': self.check_alertmanager,
            'grafana': self.check_grafana
        }

        for service_name, check_func in services.items():
            status = False
            for _ in range(self.retry_count):
                status = check_func()
                if status:
                    break
                time.sleep(self.retry_delay)
            
            self.send_alert(service_name, status)
            logger.info(f"서비스 {service_name} 상태: {'정상' if status else '비정상'}")

    def run(self) -> None:
        """헬스 체크 실행"""
        logger.info("헬스 체크 시작")
        while True:
            try:
                self.check_all_services()
            except Exception as e:
                logger.error(f"헬스 체크 실행 중 오류 발생: {str(e)}")
            
            time.sleep(self.check_interval)

if __name__ == "__main__":
    health_check = HealthCheck()
    health_check.run() 
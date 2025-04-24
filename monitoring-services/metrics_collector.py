import os
import time
import logging
import psutil
import consul
import prometheus_client
from prometheus_client import Gauge, Counter, Histogram
from datetime import datetime
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.config.fileConfig('logging.conf')
logger = logging.getLogger('monitoring')

# Prometheus 메트릭 정의
CPU_USAGE = Gauge('system_cpu_usage', 'CPU 사용량 (%)')
MEMORY_USAGE = Gauge('system_memory_usage', '메모리 사용량 (%)')
DISK_USAGE = Gauge('system_disk_usage', '디스크 사용량 (%)')
NETWORK_TRAFFIC = Counter('system_network_traffic', '네트워크 트래픽', ['direction'])
SERVICE_HEALTH = Gauge('service_health_status', '서비스 상태', ['service_name'])
REQUEST_LATENCY = Histogram('request_latency_seconds', '요청 지연 시간')

# Consul 클라이언트 설정
consul_client = consul.Consul(
    host=os.getenv('CONSUL_HOST', 'localhost'),
    port=int(os.getenv('CONSUL_PORT', 8500))
)

def collect_system_metrics():
    """시스템 메트릭 수집"""
    try:
        # CPU 사용량
        CPU_USAGE.set(psutil.cpu_percent())
        
        # 메모리 사용량
        memory = psutil.virtual_memory()
        MEMORY_USAGE.set(memory.percent)
        
        # 디스크 사용량
        disk = psutil.disk_usage('/')
        DISK_USAGE.set(disk.percent)
        
        # 네트워크 트래픽
        net_io = psutil.net_io_counters()
        NETWORK_TRAFFIC.labels(direction='incoming').inc(net_io.bytes_recv)
        NETWORK_TRAFFIC.labels(direction='outgoing').inc(net_io.bytes_sent)
        
        logger.debug("시스템 메트릭 수집 완료")
    except Exception as e:
        logger.error(f"시스템 메트릭 수집 중 오류 발생: {str(e)}")

def check_service_health():
    """서비스 상태 확인"""
    try:
        services = ['trading-service', 'backtesting-service', 'analysis-service', 'ai-prediction-service']
        
        for service in services:
            try:
                # Consul에서 서비스 상태 확인
                index, data = consul_client.health.service(service)
                if data:
                    # 서비스가 실행 중이면 1, 아니면 0
                    SERVICE_HEALTH.labels(service_name=service).set(1)
                else:
                    SERVICE_HEALTH.labels(service_name=service).set(0)
            except Exception as e:
                logger.error(f"서비스 {service} 상태 확인 중 오류 발생: {str(e)}")
                SERVICE_HEALTH.labels(service_name=service).set(0)
        
        logger.debug("서비스 상태 확인 완료")
    except Exception as e:
        logger.error(f"서비스 상태 확인 중 오류 발생: {str(e)}")

def start_metrics_collector():
    """메트릭 수집기 시작"""
    try:
        # Prometheus 메트릭 서버 시작
        prometheus_client.start_http_server(int(os.getenv('PROMETHEUS_PORT', 8000)))
        logger.info("메트릭 수집기 시작")
        
        while True:
            collect_system_metrics()
            check_service_health()
            time.sleep(int(os.getenv('METRICS_INTERVAL', 60)))
            
    except Exception as e:
        logger.error(f"메트릭 수집기 실행 중 오류 발생: {str(e)}")

if __name__ == '__main__':
    start_metrics_collector() 
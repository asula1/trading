import os
import time
import logging
import threading
import psutil
from prometheus_client import start_http_server, Gauge, Counter
from sqlalchemy.orm import Session
from typing import Optional

from .database import get_db
from .models import SystemMetrics
from .schemas import SystemMetricsCreate

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MetricsCollector:
    """시스템 메트릭 수집기"""
    
    def __init__(self):
        # Prometheus 메트릭 정의
        self.cpu_usage = Gauge('system_cpu_usage', 'CPU 사용량 (%)')
        self.memory_usage = Gauge('system_memory_usage', '메모리 사용량 (%)')
        self.disk_usage = Gauge('system_disk_usage', '디스크 사용량 (%)')
        self.network_in = Counter('system_network_in_bytes', '수신 네트워크 트래픽 (바이트)')
        self.network_out = Counter('system_network_out_bytes', '송신 네트워크 트래픽 (바이트)')
        
        # 수집 설정
        self.interval = int(os.getenv("METRICS_INTERVAL", "15"))
        self.is_running = False
        self.collector_thread: Optional[threading.Thread] = None
        
        # 네트워크 트래픽 초기값
        self.last_net_io = psutil.net_io_counters()
        self.last_collect_time = time.time()
    
    def start(self):
        """메트릭 수집 시작"""
        if self.is_running:
            logger.warning("메트릭 수집이 이미 실행 중입니다")
            return
        
        # Prometheus 메트릭 서버 시작
        prometheus_port = int(os.getenv("PROMETHEUS_METRICS_PORT", "9091"))
        start_http_server(prometheus_port)
        logger.info(f"Prometheus 메트릭 서버가 {prometheus_port} 포트에서 시작되었습니다")
        
        # 메트릭 수집 스레드 시작
        self.is_running = True
        self.collector_thread = threading.Thread(target=self._collect_metrics)
        self.collector_thread.daemon = True
        self.collector_thread.start()
        logger.info("메트릭 수집이 시작되었습니다")
    
    def stop(self):
        """메트릭 수집 중지"""
        if not self.is_running:
            logger.warning("메트릭 수집이 이미 중지되었습니다")
            return
        
        self.is_running = False
        if self.collector_thread:
            self.collector_thread.join()
        logger.info("메트릭 수집이 중지되었습니다")
    
    def _collect_metrics(self):
        """메트릭 수집 루프"""
        while self.is_running:
            try:
                # CPU 사용량
                cpu_percent = psutil.cpu_percent(interval=1)
                self.cpu_usage.set(cpu_percent)
                
                # 메모리 사용량
                memory = psutil.virtual_memory()
                memory_percent = memory.percent
                self.memory_usage.set(memory_percent)
                
                # 디스크 사용량
                disk = psutil.disk_usage('/')
                disk_percent = disk.percent
                self.disk_usage.set(disk_percent)
                
                # 네트워크 트래픽
                current_net_io = psutil.net_io_counters()
                current_time = time.time()
                time_diff = current_time - self.last_collect_time
                
                if time_diff > 0:
                    bytes_in = (current_net_io.bytes_recv - self.last_net_io.bytes_recv) / time_diff
                    bytes_out = (current_net_io.bytes_sent - self.last_net_io.bytes_sent) / time_diff
                    
                    self.network_in.inc(bytes_in)
                    self.network_out.inc(bytes_out)
                
                self.last_net_io = current_net_io
                self.last_collect_time = current_time
                
                # 데이터베이스에 메트릭 저장
                self._save_metrics(
                    cpu_percent,
                    memory_percent,
                    disk_percent,
                    current_net_io.bytes_recv,
                    current_net_io.bytes_sent
                )
                
                # 다음 수집까지 대기
                time.sleep(self.interval)
                
            except Exception as e:
                logger.error(f"메트릭 수집 중 오류 발생: {e}")
                time.sleep(self.interval)
    
    def _save_metrics(self, cpu_usage: float, memory_usage: float, disk_usage: float,
                     network_in_bytes: int, network_out_bytes: int):
        """메트릭을 데이터베이스에 저장"""
        try:
            db = next(get_db())
            metrics = SystemMetrics(
                cpu_usage=cpu_usage,
                memory_usage=memory_usage,
                disk_usage=disk_usage,
                network_in_bytes=network_in_bytes,
                network_out_bytes=network_out_bytes
            )
            db.add(metrics)
            db.commit()
        except Exception as e:
            logger.error(f"메트릭 저장 중 오류 발생: {e}")
            if db:
                db.rollback()
        finally:
            if db:
                db.close()
    
    def get_current_metrics(self) -> SystemMetricsCreate:
        """현재 메트릭 조회"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            net_io = psutil.net_io_counters()
            
            return SystemMetricsCreate(
                cpu_usage=cpu_percent,
                memory_usage=memory.percent,
                disk_usage=disk.percent,
                network_in_bytes=net_io.bytes_recv,
                network_out_bytes=net_io.bytes_sent
            )
        except Exception as e:
            logger.error(f"현재 메트릭 조회 중 오류 발생: {e}")
            raise 
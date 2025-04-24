import os
import time
import logging
import threading
import requests
from datetime import datetime
from sqlalchemy.orm import Session
from consul import Consul

from .database import get_db
from .models import ServiceStatus

logger = logging.getLogger(__name__)

class ServiceChecker:
    def __init__(self, consul_host: str = "consul", consul_port: int = 8500, check_interval: int = 30):
        self.consul_host = consul_host
        self.consul_port = consul_port
        self.check_interval = check_interval
        self.running = False
        self.thread = None
        self.consul_client = None
        
    def start(self):
        """서비스 체크 시작"""
        if self.running:
            return
            
        try:
            # Consul 클라이언트 초기화
            self.consul_client = Consul(host=self.consul_host, port=self.consul_port)
            self.running = True
            self.thread = threading.Thread(target=self._check_services)
            self.thread.daemon = True
            self.thread.start()
            logger.info(f"서비스 체커 시작 (Consul: {self.consul_host}:{self.consul_port})")
        except Exception as e:
            logger.error(f"서비스 체커 시작 중 오류 발생: {str(e)}")
            raise
            
    def stop(self):
        """서비스 체크 중지"""
        self.running = False
        if self.thread:
            self.thread.join()
        logger.info("서비스 체커 중지")
        
    def _check_services(self):
        """서비스 상태 체크 루프"""
        while self.running:
            try:
                # Consul에서 등록된 서비스 목록 가져오기
                _, services = self.consul_client.catalog.services()
                
                for service_name in services:
                    try:
                        # 서비스 상태 체크
                        is_healthy = self._check_service_health(service_name)
                        
                        # 데이터베이스에 상태 저장
                        self._save_service_status(service_name, is_healthy)
                        
                    except Exception as e:
                        logger.error(f"서비스 {service_name} 체크 중 오류 발생: {str(e)}")
                        continue
                        
            except Exception as e:
                logger.error(f"서비스 체크 루프 중 오류 발생: {str(e)}")
                
            time.sleep(self.check_interval)
            
    def _check_service_health(self, service_name: str) -> bool:
        """개별 서비스 상태 체크"""
        try:
            # Consul에서 서비스 정보 가져오기
            _, nodes = self.consul_client.catalog.service(service_name)
            
            if not nodes:
                return False
                
            # 첫 번째 노드의 상태 체크
            node = nodes[0]
            service_address = node['ServiceAddress']
            service_port = node['ServicePort']
            
            # 서비스 엔드포인트 체크
            health_url = f"http://{service_address}:{service_port}/health"
            response = requests.get(health_url, timeout=5)
            
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"서비스 {service_name} 상태 체크 중 오류 발생: {str(e)}")
            return False
            
    def _save_service_status(self, service_name: str, is_healthy: bool):
        """서비스 상태를 데이터베이스에 저장"""
        try:
            db: Session = next(get_db())
            service_status = ServiceStatus(
                service_name=service_name,
                is_healthy=is_healthy,
                last_check=datetime.now()
            )
            db.add(service_status)
            db.commit()
        except Exception as e:
            logger.error(f"서비스 상태 저장 중 오류 발생: {str(e)}")
            if db:
                db.rollback()
        finally:
            if db:
                db.close()
                
    def get_service_status(self, service_name: str) -> dict:
        """특정 서비스의 최신 상태 조회"""
        try:
            db: Session = next(get_db())
            status = db.query(ServiceStatus)\
                .filter(ServiceStatus.service_name == service_name)\
                .order_by(ServiceStatus.last_check.desc())\
                .first()
                
            if status:
                return {
                    "service_name": status.service_name,
                    "is_healthy": status.is_healthy,
                    "last_check": status.last_check
                }
            return None
            
        except Exception as e:
            logger.error(f"서비스 상태 조회 중 오류 발생: {str(e)}")
            return None
        finally:
            if db:
                db.close()
                
    def get_all_service_statuses(self) -> list:
        """모든 서비스의 최신 상태 조회"""
        try:
            db: Session = next(get_db())
            statuses = db.query(ServiceStatus)\
                .order_by(ServiceStatus.last_check.desc())\
                .all()
                
            return [{
                "service_name": status.service_name,
                "is_healthy": status.is_healthy,
                "last_check": status.last_check
            } for status in statuses]
            
        except Exception as e:
            logger.error(f"서비스 상태 목록 조회 중 오류 발생: {str(e)}")
            return []
        finally:
            if db:
                db.close() 
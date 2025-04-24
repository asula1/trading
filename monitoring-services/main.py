import os
import logging
import asyncio
import psutil
from datetime import datetime
from typing import List, Optional, Dict
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, Gauge, start_http_server
import consul
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv
import aiohttp
import json
from metrics_collector import start_metrics_collector
from alert_manager import AlertManager
from api import app as api_app
import uvicorn

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.config.fileConfig('logging.conf')
logger = logging.getLogger('monitoring')

# SQLAlchemy 설정
SQLALCHEMY_DATABASE_URL = f"postgresql://{os.getenv('DB_USER', 'postgres')}:{os.getenv('DB_PASSWORD', 'postgres')}@{os.getenv('DB_HOST', 'postgres')}/{os.getenv('DB_NAME', 'tradingdb')}"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 데이터베이스 모델 정의
class SystemMetric(Base):
    __tablename__ = "system_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    cpu_usage = Column(Float)
    memory_usage = Column(Float)
    disk_usage = Column(Float)
    network_incoming = Column(Integer)
    network_outgoing = Column(Integer)

class ServiceStatus(Base):
    __tablename__ = "service_status"
    
    id = Column(Integer, primary_key=True, index=True)
    service_name = Column(String, index=True)
    status = Column(String)
    last_check = Column(DateTime, default=datetime.utcnow)
    details = Column(JSON)

class Alert(Base):
    __tablename__ = "alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    service = Column(String, index=True)
    severity = Column(String)
    message = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    resolved = Column(Boolean, default=False)

# 데이터베이스 테이블 생성
Base.metadata.create_all(bind=engine)

# Prometheus 메트릭 정의
REQUEST_COUNT = Counter('monitoring_request_total', 'Total monitoring requests')
LATENCY = Histogram('monitoring_request_latency_seconds', 'Request latency in seconds')
CPU_USAGE = Gauge('system_cpu_usage', 'CPU usage percentage')
MEMORY_USAGE = Gauge('system_memory_usage', 'Memory usage percentage')
DISK_USAGE = Gauge('system_disk_usage', 'Disk usage percentage')
NETWORK_TRAFFIC = Gauge('system_network_traffic', 'Network traffic in bytes', ['direction'])
SERVICE_HEALTH = Gauge('service_health_status', 'Service health status', ['service_name'])

# FastAPI 앱 초기화
app = FastAPI(
    title="Trading System Monitoring Service",
    description="트레이딩 시스템 모니터링 서비스",
    version="1.0.0"
)

# Consul 클라이언트 초기화
consul_client = consul.Consul(host=os.getenv('CONSUL_HOST', 'consul'))

# 의존성 함수
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 모델 정의
class ServiceHealth(BaseModel):
    service_name: str
    status: str
    last_check: datetime
    details: Optional[dict]

    class Config:
        orm_mode = True

class SystemMetrics(BaseModel):
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    network_traffic: dict

    class Config:
        orm_mode = True

class AlertResponse(BaseModel):
    id: int
    service: str
    severity: str
    message: str
    timestamp: datetime
    resolved: bool

    class Config:
        orm_mode = True

# 메트릭 수집 함수
async def collect_metrics(db: Session):
    while True:
        try:
            # 시스템 메트릭 수집
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            net_io = psutil.net_io_counters()
            
            # Prometheus 메트릭 업데이트
            CPU_USAGE.set(cpu_percent)
            MEMORY_USAGE.set(memory.percent)
            DISK_USAGE.set(disk.percent)
            NETWORK_TRAFFIC.labels(direction='incoming').set(net_io.bytes_recv)
            NETWORK_TRAFFIC.labels(direction='outgoing').set(net_io.bytes_sent)
            
            # 데이터베이스에 메트릭 저장
            metric = SystemMetric(
                cpu_usage=cpu_percent,
                memory_usage=memory.percent,
                disk_usage=disk.percent,
                network_incoming=net_io.bytes_recv,
                network_outgoing=net_io.bytes_sent
            )
            db.add(metric)
            db.commit()
            
            # 임계값 체크 및 알림 생성
            thresholds = {
                'cpu': float(os.getenv('CPU_THRESHOLD', 80)),
                'memory': float(os.getenv('MEMORY_THRESHOLD', 80)),
                'disk': float(os.getenv('DISK_THRESHOLD', 80))
            }
            
            if cpu_percent > thresholds['cpu']:
                await create_alert(db, 'system', 'warning', f'High CPU usage: {cpu_percent}%')
            if memory.percent > thresholds['memory']:
                await create_alert(db, 'system', 'warning', f'High memory usage: {memory.percent}%')
            if disk.percent > thresholds['disk']:
                await create_alert(db, 'system', 'warning', f'High disk usage: {disk.percent}%')
            
            await asyncio.sleep(int(os.getenv('METRICS_INTERVAL', 60)))
        except Exception as e:
            logger.error(f"Error collecting metrics: {str(e)}")
            await asyncio.sleep(60)

# 서비스 상태 체크 함수
async def check_services(db: Session):
    while True:
        try:
            services = consul_client.agent.services()
            for service_id, service_info in services.items():
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            f"http://{service_info['Address']}:{service_info['Port']}/health"
                        ) as response:
                            status = 'passing' if response.status == 200 else 'critical'
                            SERVICE_HEALTH.labels(service_name=service_info['Service']).set(
                                1 if status == 'passing' else 0
                            )
                            
                            # 서비스 상태 저장
                            service_status = ServiceStatus(
                                service_name=service_info['Service'],
                                status=status,
                                details={
                                    'address': service_info['Address'],
                                    'port': service_info['Port'],
                                    'tags': service_info.get('Tags', [])
                                }
                            )
                            db.add(service_status)
                            db.commit()
                            
                            if status == 'critical':
                                await create_alert(
                                    db,
                                    service_info['Service'],
                                    'critical',
                                    f'Service {service_info["Service"]} is down'
                                )
                except Exception as e:
                    logger.error(f"Error checking service {service_info['Service']}: {str(e)}")
                    SERVICE_HEALTH.labels(service_name=service_info['Service']).set(0)
            
            await asyncio.sleep(int(os.getenv('HEALTH_CHECK_INTERVAL', 30)))
        except Exception as e:
            logger.error(f"Error checking services: {str(e)}")
            await asyncio.sleep(30)

# 알림 생성 함수
async def create_alert(db: Session, service: str, severity: str, message: str):
    try:
        alert = Alert(
            service=service,
            severity=severity,
            message=message
        )
        db.add(alert)
        db.commit()
        logger.info(f"Created alert for {service}: {message}")
    except Exception as e:
        logger.error(f"Error creating alert: {str(e)}")

# API 엔드포인트
@app.get("/")
async def root():
    return {"message": "Trading System Monitoring Service"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/services/health", response_model=List[ServiceHealth])
async def get_services_health(db: Session = Depends(get_db)):
    REQUEST_COUNT.inc()
    try:
        services = db.query(ServiceStatus).order_by(ServiceStatus.last_check.desc()).limit(100).all()
        return services
    except Exception as e:
        logger.error(f"Error getting services health: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/metrics/system", response_model=SystemMetrics)
async def get_system_metrics(db: Session = Depends(get_db)):
    REQUEST_COUNT.inc()
    try:
        metric = db.query(SystemMetric).order_by(SystemMetric.timestamp.desc()).first()
        if metric:
            return SystemMetrics(
                cpu_usage=metric.cpu_usage,
                memory_usage=metric.memory_usage,
                disk_usage=metric.disk_usage,
                network_traffic={
                    "incoming": metric.network_incoming,
                    "outgoing": metric.network_outgoing
                }
            )
        else:
            return SystemMetrics(
                cpu_usage=psutil.cpu_percent(),
                memory_usage=psutil.virtual_memory().percent,
                disk_usage=psutil.disk_usage('/').percent,
                network_traffic={
                    "incoming": psutil.net_io_counters().bytes_recv,
                    "outgoing": psutil.net_io_counters().bytes_sent
                }
            )
    except Exception as e:
        logger.error(f"Error getting system metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/alerts", response_model=List[AlertResponse])
async def get_alerts(resolved: bool = False, db: Session = Depends(get_db)):
    try:
        alerts = db.query(Alert).filter(Alert.resolved == resolved).order_by(Alert.timestamp.desc()).limit(100).all()
        return alerts
    except Exception as e:
        logger.error(f"Error getting alerts: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: int, db: Session = Depends(get_db)):
    try:
        alert = db.query(Alert).filter(Alert.id == alert_id).first()
        if alert:
            alert.resolved = True
            db.commit()
            return {"message": f"Alert {alert_id} resolved"}
        else:
            raise HTTPException(status_code=404, detail="Alert not found")
    except Exception as e:
        logger.error(f"Error resolving alert: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# 메트릭 수집기 시작
async def start_metrics_collector_task():
    """메트릭 수집기 비동기 작업 시작"""
    try:
        await asyncio.to_thread(start_metrics_collector)
    except Exception as e:
        logger.error(f"메트릭 수집기 시작 중 오류 발생: {str(e)}")

# 알림 관리자 시작
async def start_alert_manager_task():
    """알림 관리자 비동기 작업 시작"""
    try:
        alert_manager = AlertManager()
        while True:
            try:
                # 메트릭 수집 (실제 구현에서는 metrics_collector.py에서 가져와야 함)
                metrics = {
                    'cpu': psutil.cpu_percent(),
                    'memory': psutil.virtual_memory().percent,
                    'disk': psutil.disk_usage('/').percent
                }
                
                alert_manager.process_alerts(metrics)
                alert_manager.cleanup_old_alerts()
                
                await asyncio.sleep(int(os.getenv('ALERT_CHECK_INTERVAL', 60)))
            except Exception as e:
                logger.error(f"알림 처리 중 오류 발생: {str(e)}")
                await asyncio.sleep(60)
    except Exception as e:
        logger.error(f"알림 관리자 시작 중 오류 발생: {str(e)}")

@app.on_event("startup")
async def startup_event():
    """서비스 시작 시 실행되는 이벤트"""
    logger.info("모니터링 서비스 시작")
    
    # 메트릭 수집기 시작
    asyncio.create_task(start_metrics_collector_task())
    
    # 알림 관리자 시작
    asyncio.create_task(start_alert_manager_task())

    # Prometheus 메트릭 서버 시작
    start_http_server(int(os.getenv('PROMETHEUS_PORT', 8000)))
    
    # 메트릭 수집 및 서비스 체크 태스크 시작
    db = SessionLocal()
    asyncio.create_task(collect_metrics(db))
    asyncio.create_task(check_services(db))
    
    # Consul에 서비스 등록
    consul_client.agent.service.register(
        os.getenv('SERVICE_NAME', 'monitoring-service'),
        service_id=f"{os.getenv('SERVICE_NAME', 'monitoring-service')}-1",
        port=int(os.getenv('SERVICE_PORT', 8090)),
        tags=['monitoring', 'metrics']
    )

@app.on_event("shutdown")
async def shutdown_event():
    """서비스 종료 시 실행되는 이벤트"""
    logger.info("모니터링 서비스 종료")
    
    # Consul에서 서비스 등록 해제
    consul_client.agent.service.deregister(f"{os.getenv('SERVICE_NAME', 'monitoring-service')}-1")

if __name__ == "__main__":
    # 서버 시작
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv('API_PORT', 8090)),
        reload=bool(os.getenv('DEBUG', False))
    ) 
import os
import logging
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta

from .database import get_db, init_db
from .metrics_collector import MetricsCollector
from .service_checker import ServiceChecker
from .alert_manager import AlertManager
from .models import SystemMetrics, ServiceStatus, AlertConfig, AlertHistory
from .schemas import (
    SystemMetricsResponse,
    ServiceStatusResponse,
    AlertConfigCreate,
    AlertConfigResponse,
    AlertHistoryResponse,
    ErrorResponse,
    SuccessResponse
)

# 로깅 설정
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format=os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
)
logger = logging.getLogger(__name__)

# FastAPI 애플리케이션 생성
app = FastAPI(
    title="모니터링 서비스",
    description="시스템 리소스와 서비스 상태를 모니터링하는 API",
    version="1.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 전역 인스턴스
metrics_collector = None
service_checker = None
alert_manager = None

@app.on_event("startup")
async def startup_event():
    """애플리케이션 시작 시 초기화"""
    global metrics_collector, service_checker, alert_manager
    
    # 데이터베이스 초기화
    init_db()
    
    # 메트릭 수집기 초기화
    metrics_collector = MetricsCollector(
        interval=int(os.getenv("METRICS_INTERVAL", 15)),
        prometheus_port=int(os.getenv("PROMETHEUS_METRICS_PORT", 9091))
    )
    metrics_collector.start()
    
    # 서비스 체커 초기화
    service_checker = ServiceChecker(
        consul_host=os.getenv("CONSUL_HOST", "consul"),
        consul_port=int(os.getenv("CONSUL_PORT", 8500)),
        check_interval=int(os.getenv("SERVICE_CHECK_INTERVAL", 30))
    )
    service_checker.start()
    
    # 알림 매니저 초기화
    alert_manager = AlertManager(
        cooldown_period=int(os.getenv("ALERT_COOLDOWN_PERIOD", 300))
    )

@app.on_event("shutdown")
async def shutdown_event():
    """애플리케이션 종료 시 정리"""
    if metrics_collector:
        metrics_collector.stop()
    if service_checker:
        service_checker.stop()

@app.get("/health")
async def health_check():
    """서비스 상태 확인"""
    return {"status": "healthy"}

@app.get("/metrics/system", response_model=List[SystemMetricsResponse])
async def get_system_metrics(
    db: Session = Depends(get_db),
    start_time: datetime = None,
    end_time: datetime = None
):
    """시스템 메트릭 조회"""
    try:
        query = db.query(SystemMetrics)
        if start_time:
            query = query.filter(SystemMetrics.timestamp >= start_time)
        if end_time:
            query = query.filter(SystemMetrics.timestamp <= end_time)
        metrics = query.order_by(SystemMetrics.timestamp.desc()).all()
        return metrics
    except Exception as e:
        logger.error(f"시스템 메트릭 조회 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/metrics/service", response_model=List[ServiceStatusResponse])
async def get_service_status(
    db: Session = Depends(get_db),
    service_name: str = None
):
    """서비스 상태 조회"""
    try:
        query = db.query(ServiceStatus)
        if service_name:
            query = query.filter(ServiceStatus.service_name == service_name)
        status = query.order_by(ServiceStatus.last_check.desc()).all()
        return status
    except Exception as e:
        logger.error(f"서비스 상태 조회 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/alerts/config", response_model=List[AlertConfigResponse])
async def get_alert_configs(db: Session = Depends(get_db)):
    """알림 설정 조회"""
    try:
        configs = db.query(AlertConfig).all()
        return configs
    except Exception as e:
        logger.error(f"알림 설정 조회 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/alerts/config", response_model=AlertConfigResponse)
async def create_alert_config(
    config: AlertConfigCreate,
    db: Session = Depends(get_db)
):
    """알림 설정 생성"""
    try:
        db_config = AlertConfig(**config.dict())
        db.add(db_config)
        db.commit()
        db.refresh(db_config)
        return db_config
    except Exception as e:
        db.rollback()
        logger.error(f"알림 설정 생성 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/alerts/history", response_model=List[AlertHistoryResponse])
async def get_alert_history(
    db: Session = Depends(get_db),
    start_time: datetime = None,
    end_time: datetime = None,
    alert_type: str = None
):
    """알림 이력 조회"""
    try:
        query = db.query(AlertHistory)
        if start_time:
            query = query.filter(AlertHistory.timestamp >= start_time)
        if end_time:
            query = query.filter(AlertHistory.timestamp <= end_time)
        if alert_type:
            query = query.filter(AlertHistory.alert_type == alert_type)
        history = query.order_by(AlertHistory.timestamp.desc()).all()
        return history
    except Exception as e:
        logger.error(f"알림 이력 조회 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/alerts/test")
async def send_test_alert(
    alert_type: str,
    severity: str = "warning",
    message: str = "테스트 알림"
):
    """테스트 알림 전송"""
    try:
        if alert_manager:
            alert_manager.send_alert(alert_type, severity, message)
            return {"status": "success", "message": "테스트 알림이 전송되었습니다."}
        else:
            raise HTTPException(status_code=500, detail="알림 매니저가 초기화되지 않았습니다.")
    except Exception as e:
        logger.error(f"테스트 알림 전송 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", 8000))
    ) 
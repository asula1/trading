from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta

from .database import get_db
from .models import (
    SystemMetrics, ServiceStatus, AlertConfig, AlertHistory,
    ServiceMetrics, ServiceEndpoint, EndpointMetrics
)
from .schemas import (
    SystemMetricsCreate, SystemMetricsResponse,
    ServiceStatusCreate, ServiceStatusResponse,
    AlertConfigCreate, AlertConfigUpdate, AlertConfigResponse,
    AlertHistoryCreate, AlertHistoryResponse,
    ServiceMetricsCreate, ServiceMetricsResponse,
    ServiceEndpointCreate, ServiceEndpointResponse,
    EndpointMetricsCreate, EndpointMetricsResponse,
    ErrorResponse, SuccessResponse
)

router = APIRouter()

# 시스템 메트릭 API
@router.post("/metrics/system", response_model=SystemMetricsResponse)
async def create_system_metrics(
    metrics: SystemMetricsCreate,
    db: Session = Depends(get_db)
):
    """시스템 메트릭 생성"""
    try:
        db_metrics = SystemMetrics(**metrics.dict())
        db.add(db_metrics)
        db.commit()
        db.refresh(db_metrics)
        return db_metrics
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/metrics/system", response_model=List[SystemMetricsResponse])
async def get_system_metrics(
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """시스템 메트릭 조회"""
    query = db.query(SystemMetrics)
    if start_time:
        query = query.filter(SystemMetrics.timestamp >= start_time)
    if end_time:
        query = query.filter(SystemMetrics.timestamp <= end_time)
    return query.order_by(SystemMetrics.timestamp.desc()).limit(limit).all()

# 서비스 상태 API
@router.post("/services/status", response_model=ServiceStatusResponse)
async def create_service_status(
    status: ServiceStatusCreate,
    db: Session = Depends(get_db)
):
    """서비스 상태 생성"""
    try:
        db_status = ServiceStatus(**status.dict())
        db.add(db_status)
        db.commit()
        db.refresh(db_status)
        return db_status
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/services/status", response_model=List[ServiceStatusResponse])
async def get_service_status(
    service_name: Optional[str] = None,
    is_healthy: Optional[bool] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """서비스 상태 조회"""
    query = db.query(ServiceStatus)
    if service_name:
        query = query.filter(ServiceStatus.service_name == service_name)
    if is_healthy is not None:
        query = query.filter(ServiceStatus.is_healthy == is_healthy)
    return query.order_by(ServiceStatus.last_check.desc()).limit(limit).all()

# 알림 설정 API
@router.post("/alerts/config", response_model=AlertConfigResponse)
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/alerts/config", response_model=List[AlertConfigResponse])
async def get_alert_configs(
    alert_type: Optional[str] = None,
    enabled: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """알림 설정 조회"""
    query = db.query(AlertConfig)
    if alert_type:
        query = query.filter(AlertConfig.alert_type == alert_type)
    if enabled is not None:
        query = query.filter(AlertConfig.enabled == enabled)
    return query.all()

@router.put("/alerts/config/{config_id}", response_model=AlertConfigResponse)
async def update_alert_config(
    config_id: int,
    config: AlertConfigUpdate,
    db: Session = Depends(get_db)
):
    """알림 설정 업데이트"""
    db_config = db.query(AlertConfig).filter(AlertConfig.id == config_id).first()
    if not db_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="알림 설정을 찾을 수 없습니다."
        )
    try:
        for key, value in config.dict(exclude_unset=True).items():
            setattr(db_config, key, value)
        db.commit()
        db.refresh(db_config)
        return db_config
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# 알림 이력 API
@router.post("/alerts/history", response_model=AlertHistoryResponse)
async def create_alert_history(
    history: AlertHistoryCreate,
    db: Session = Depends(get_db)
):
    """알림 이력 생성"""
    try:
        db_history = AlertHistory(**history.dict())
        db.add(db_history)
        db.commit()
        db.refresh(db_history)
        return db_history
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/alerts/history", response_model=List[AlertHistoryResponse])
async def get_alert_history(
    alert_type: Optional[str] = None,
    severity: Optional[str] = None,
    resolved: Optional[bool] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """알림 이력 조회"""
    query = db.query(AlertHistory)
    if alert_type:
        query = query.filter(AlertHistory.alert_type == alert_type)
    if severity:
        query = query.filter(AlertHistory.severity == severity)
    if resolved is not None:
        query = query.filter(AlertHistory.resolved == resolved)
    if start_time:
        query = query.filter(AlertHistory.timestamp >= start_time)
    if end_time:
        query = query.filter(AlertHistory.timestamp <= end_time)
    return query.order_by(AlertHistory.timestamp.desc()).limit(limit).all()

@router.put("/alerts/history/{history_id}/resolve", response_model=AlertHistoryResponse)
async def resolve_alert(
    history_id: int,
    resolved_by: str,
    db: Session = Depends(get_db)
):
    """알림 해결"""
    db_history = db.query(AlertHistory).filter(AlertHistory.id == history_id).first()
    if not db_history:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="알림 이력을 찾을 수 없습니다."
        )
    try:
        db_history.resolved = True
        db_history.resolved_by = resolved_by
        db_history.resolved_at = datetime.utcnow()
        db.commit()
        db.refresh(db_history)
        return db_history
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# 서비스 메트릭 API
@router.post("/metrics/service", response_model=ServiceMetricsResponse)
async def create_service_metrics(
    metrics: ServiceMetricsCreate,
    db: Session = Depends(get_db)
):
    """서비스 메트릭 생성"""
    try:
        db_metrics = ServiceMetrics(**metrics.dict())
        db.add(db_metrics)
        db.commit()
        db.refresh(db_metrics)
        return db_metrics
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/metrics/service", response_model=List[ServiceMetricsResponse])
async def get_service_metrics(
    service_name: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """서비스 메트릭 조회"""
    query = db.query(ServiceMetrics)
    if service_name:
        query = query.filter(ServiceMetrics.service_name == service_name)
    if start_time:
        query = query.filter(ServiceMetrics.timestamp >= start_time)
    if end_time:
        query = query.filter(ServiceMetrics.timestamp <= end_time)
    return query.order_by(ServiceMetrics.timestamp.desc()).limit(limit).all()

# 서비스 엔드포인트 API
@router.post("/endpoints", response_model=ServiceEndpointResponse)
async def create_endpoint(
    endpoint: ServiceEndpointCreate,
    db: Session = Depends(get_db)
):
    """서비스 엔드포인트 생성"""
    try:
        db_endpoint = ServiceEndpoint(**endpoint.dict())
        db.add(db_endpoint)
        db.commit()
        db.refresh(db_endpoint)
        return db_endpoint
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/endpoints", response_model=List[ServiceEndpointResponse])
async def get_endpoints(
    service_name: Optional[str] = None,
    is_monitored: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """서비스 엔드포인트 조회"""
    query = db.query(ServiceEndpoint)
    if service_name:
        query = query.filter(ServiceEndpoint.service_name == service_name)
    if is_monitored is not None:
        query = query.filter(ServiceEndpoint.is_monitored == is_monitored)
    return query.all()

# 엔드포인트 메트릭 API
@router.post("/metrics/endpoint", response_model=EndpointMetricsResponse)
async def create_endpoint_metrics(
    metrics: EndpointMetricsCreate,
    db: Session = Depends(get_db)
):
    """엔드포인트 메트릭 생성"""
    try:
        db_metrics = EndpointMetrics(**metrics.dict())
        db.add(db_metrics)
        db.commit()
        db.refresh(db_metrics)
        return db_metrics
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/metrics/endpoint", response_model=List[EndpointMetricsResponse])
async def get_endpoint_metrics(
    endpoint_id: Optional[int] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """엔드포인트 메트릭 조회"""
    query = db.query(EndpointMetrics)
    if endpoint_id:
        query = query.filter(EndpointMetrics.endpoint_id == endpoint_id)
    if start_time:
        query = query.filter(EndpointMetrics.timestamp >= start_time)
    if end_time:
        query = query.filter(EndpointMetrics.timestamp <= end_time)
    return query.order_by(EndpointMetrics.timestamp.desc()).limit(limit).all() 
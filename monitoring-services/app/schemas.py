from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
from datetime import datetime

class SystemMetricsBase(BaseModel):
    """시스템 메트릭 기본 스키마"""
    cpu_usage: float = Field(..., ge=0, le=100, description="CPU 사용률 (%)")
    memory_usage: float = Field(..., ge=0, le=100, description="메모리 사용률 (%)")
    disk_usage: float = Field(..., ge=0, le=100, description="디스크 사용률 (%)")
    network_in: float = Field(..., ge=0, description="네트워크 수신량 (bytes)")
    network_out: float = Field(..., ge=0, description="네트워크 송신량 (bytes)")

class SystemMetricsCreate(SystemMetricsBase):
    """시스템 메트릭 생성 스키마"""
    pass

class SystemMetricsResponse(SystemMetricsBase):
    """시스템 메트릭 응답 스키마"""
    id: int
    timestamp: datetime

    class Config:
        orm_mode = True

class ServiceStatusBase(BaseModel):
    """서비스 상태 기본 스키마"""
    service_name: str = Field(..., min_length=1, max_length=100, description="서비스 이름")
    is_healthy: bool = Field(..., description="서비스 건강 상태")
    response_time: Optional[float] = Field(None, ge=0, description="응답 시간 (초)")
    error_message: Optional[str] = Field(None, description="에러 메시지")

class ServiceStatusCreate(ServiceStatusBase):
    """서비스 상태 생성 스키마"""
    pass

class ServiceStatusResponse(ServiceStatusBase):
    """서비스 상태 응답 스키마"""
    id: int
    last_check: datetime

    class Config:
        orm_mode = True

class AlertConfigBase(BaseModel):
    """알림 설정 기본 스키마"""
    alert_type: str = Field(..., min_length=1, max_length=100, description="알림 유형")
    enabled: bool = Field(True, description="알림 활성화 여부")
    email_enabled: bool = Field(True, description="이메일 알림 활성화 여부")
    slack_enabled: bool = Field(True, description="Slack 알림 활성화 여부")
    email_recipients: List[EmailStr] = Field(default=[], description="이메일 수신자 목록")
    severity: str = Field("warning", description="알림 심각도")
    threshold: Optional[float] = Field(None, ge=0, description="알림 임계값")
    cooldown_period: int = Field(300, ge=0, description="쿨다운 기간 (초)")

class AlertConfigCreate(AlertConfigBase):
    """알림 설정 생성 스키마"""
    pass

class AlertConfigUpdate(AlertConfigBase):
    """알림 설정 업데이트 스키마"""
    pass

class AlertConfigResponse(AlertConfigBase):
    """알림 설정 응답 스키마"""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

class AlertHistoryBase(BaseModel):
    """알림 이력 기본 스키마"""
    alert_type: str = Field(..., min_length=1, max_length=100, description="알림 유형")
    severity: str = Field(..., min_length=1, max_length=20, description="알림 심각도")
    message: str = Field(..., min_length=1, description="알림 메시지")
    resolved: bool = Field(False, description="해결 여부")
    resolved_by: Optional[str] = Field(None, min_length=1, max_length=100, description="해결자")

class AlertHistoryCreate(AlertHistoryBase):
    """알림 이력 생성 스키마"""
    pass

class AlertHistoryResponse(AlertHistoryBase):
    """알림 이력 응답 스키마"""
    id: int
    timestamp: datetime
    resolved_at: Optional[datetime]

    class Config:
        orm_mode = True

class ServiceMetricsBase(BaseModel):
    """서비스 메트릭 기본 스키마"""
    service_name: str = Field(..., min_length=1, max_length=100, description="서비스 이름")
    request_count: int = Field(0, ge=0, description="요청 수")
    error_count: int = Field(0, ge=0, description="에러 수")
    avg_response_time: Optional[float] = Field(None, ge=0, description="평균 응답 시간 (초)")
    max_response_time: Optional[float] = Field(None, ge=0, description="최대 응답 시간 (초)")
    min_response_time: Optional[float] = Field(None, ge=0, description="최소 응답 시간 (초)")

class ServiceMetricsCreate(ServiceMetricsBase):
    """서비스 메트릭 생성 스키마"""
    pass

class ServiceMetricsResponse(ServiceMetricsBase):
    """서비스 메트릭 응답 스키마"""
    id: int
    timestamp: datetime

    class Config:
        orm_mode = True

class ServiceEndpointBase(BaseModel):
    """서비스 엔드포인트 기본 스키마"""
    service_name: str = Field(..., min_length=1, max_length=100, description="서비스 이름")
    endpoint_path: str = Field(..., min_length=1, max_length=200, description="엔드포인트 경로")
    method: str = Field(..., min_length=1, max_length=10, description="HTTP 메서드")
    is_monitored: bool = Field(True, description="모니터링 여부")

class ServiceEndpointCreate(ServiceEndpointBase):
    """서비스 엔드포인트 생성 스키마"""
    pass

class ServiceEndpointResponse(ServiceEndpointBase):
    """서비스 엔드포인트 응답 스키마"""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

class EndpointMetricsBase(BaseModel):
    """엔드포인트 메트릭 기본 스키마"""
    request_count: int = Field(0, ge=0, description="요청 수")
    error_count: int = Field(0, ge=0, description="에러 수")
    avg_response_time: Optional[float] = Field(None, ge=0, description="평균 응답 시간 (초)")
    max_response_time: Optional[float] = Field(None, ge=0, description="최대 응답 시간 (초)")
    min_response_time: Optional[float] = Field(None, ge=0, description="최소 응답 시간 (초)")

class EndpointMetricsCreate(EndpointMetricsBase):
    """엔드포인트 메트릭 생성 스키마"""
    endpoint_id: int = Field(..., gt=0, description="엔드포인트 ID")

class EndpointMetricsResponse(EndpointMetricsBase):
    """엔드포인트 메트릭 응답 스키마"""
    id: int
    endpoint_id: int
    timestamp: datetime

    class Config:
        orm_mode = True

class ErrorResponse(BaseModel):
    """에러 응답 스키마"""
    error: str = Field(..., description="에러 메시지")
    status_code: int = Field(..., ge=400, le=599, description="HTTP 상태 코드")

class SuccessResponse(BaseModel):
    """성공 응답 스키마"""
    message: str = Field(..., description="성공 메시지")
    status_code: int = Field(200, ge=200, le=299, description="HTTP 상태 코드") 
from datetime import datetime
from sqlalchemy import Column, Integer, Float, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class SystemMetrics(Base):
    """시스템 메트릭 모델"""
    __tablename__ = "system_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.now, index=True)
    cpu_usage = Column(Float, nullable=False)
    memory_usage = Column(Float, nullable=False)
    disk_usage = Column(Float, nullable=False)
    network_in = Column(Float, nullable=False)
    network_out = Column(Float, nullable=False)
    
class ServiceStatus(Base):
    """서비스 상태 모델"""
    __tablename__ = "service_status"
    
    id = Column(Integer, primary_key=True, index=True)
    service_name = Column(String(100), nullable=False, index=True)
    is_healthy = Column(Boolean, nullable=False)
    last_check = Column(DateTime, default=datetime.now, index=True)
    response_time = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)
    
class AlertConfig(Base):
    """알림 설정 모델"""
    __tablename__ = "alert_config"
    
    id = Column(Integer, primary_key=True, index=True)
    alert_type = Column(String(100), nullable=False, unique=True, index=True)
    enabled = Column(Boolean, default=True)
    email_enabled = Column(Boolean, default=True)
    slack_enabled = Column(Boolean, default=True)
    email_recipients = Column(Text, nullable=True)  # JSON 문자열로 저장
    severity = Column(String(20), default="warning")
    threshold = Column(Float, nullable=True)
    cooldown_period = Column(Integer, default=300)  # 초 단위
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
class AlertHistory(Base):
    """알림 이력 모델"""
    __tablename__ = "alert_history"
    
    id = Column(Integer, primary_key=True, index=True)
    alert_type = Column(String(100), nullable=False, index=True)
    severity = Column(String(20), nullable=False)
    message = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.now, index=True)
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String(100), nullable=True)
    
class ServiceMetrics(Base):
    """서비스 메트릭 모델"""
    __tablename__ = "service_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    service_name = Column(String(100), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.now, index=True)
    request_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    avg_response_time = Column(Float, nullable=True)
    max_response_time = Column(Float, nullable=True)
    min_response_time = Column(Float, nullable=True)
    
class ServiceEndpoint(Base):
    """서비스 엔드포인트 모델"""
    __tablename__ = "service_endpoints"
    
    id = Column(Integer, primary_key=True, index=True)
    service_name = Column(String(100), nullable=False, index=True)
    endpoint_path = Column(String(200), nullable=False)
    method = Column(String(10), nullable=False)
    is_monitored = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
class EndpointMetrics(Base):
    """엔드포인트 메트릭 모델"""
    __tablename__ = "endpoint_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    endpoint_id = Column(Integer, ForeignKey("service_endpoints.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.now, index=True)
    request_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    avg_response_time = Column(Float, nullable=True)
    max_response_time = Column(Float, nullable=True)
    min_response_time = Column(Float, nullable=True)
    
    endpoint = relationship("ServiceEndpoint", backref="metrics") 
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api import app
from models import SystemMetrics, ServiceStatus, AlertConfig, AlertHistory
from app.database import Base, get_db
from app.models import (
    ServiceMetrics, ServiceEndpoint, EndpointMetrics
)

# 테스트 데이터베이스 설정
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 테스트 데이터베이스 초기화
def init_test_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        # 기본 알림 설정 생성
        alert_configs = [
            AlertConfig(
                alert_type="high_cpu_usage",
                enabled=True,
                email_enabled=True,
                slack_enabled=True,
                email_recipients="[]",
                severity="warning",
                threshold=80.0,
                cooldown_period=300
            ),
            AlertConfig(
                alert_type="service_down",
                enabled=True,
                email_enabled=True,
                slack_enabled=True,
                email_recipients="[]",
                severity="critical",
                threshold=None,
                cooldown_period=300
            )
        ]
        for config in alert_configs:
            db.add(config)
        db.commit()
    finally:
        db.close()

# 테스트 클라이언트 설정
@pytest.fixture
def client():
    init_test_db()
    def override_get_db():
        try:
            db = TestingSessionLocal()
            yield db
        finally:
            db.close()
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture
def mock_metrics_collector():
    with patch('metrics_collector.collect_system_metrics') as mock_collect:
        mock_collect.return_value = {
            'cpu_usage': 50.0,
            'memory_usage': 60.0,
            'disk_usage': 70.0,
            'network_traffic': {
                'incoming': 1000,
                'outgoing': 2000
            }
        }
        yield mock_collect

@pytest.fixture
def mock_service_checker():
    with patch('metrics_collector.check_service_health') as mock_check:
        mock_check.return_value = [
            {
                'service_name': 'test-service',
                'status': 'healthy',
                'tags': ['primary']
            }
        ]
        yield mock_check

@pytest.fixture
def mock_alert_manager():
    with patch('alert_manager.AlertManager') as mock_manager:
        mock_instance = MagicMock()
        mock_manager.return_value = mock_instance
        yield mock_instance

def test_api_status():
    """API 상태 확인 테스트"""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_get_system_metrics(mock_metrics_collector):
    """시스템 메트릭 조회 테스트"""
    response = client.get("/metrics/system")
    assert response.status_code == 200
    
    data = response.json()
    assert data['cpu_usage'] == 50.0
    assert data['memory_usage'] == 60.0
    assert data['disk_usage'] == 70.0
    assert data['network_traffic']['incoming'] == 1000
    assert data['network_traffic']['outgoing'] == 2000

def test_get_service_status(mock_service_checker):
    """서비스 상태 조회 테스트"""
    response = client.get("/services/status")
    assert response.status_code == 200
    
    data = response.json()
    assert len(data) == 1
    assert data[0]['service_name'] == 'test-service'
    assert data[0]['status'] == 'healthy'
    assert data[0]['tags'] == ['primary']

def test_get_alert_config(mock_alert_manager):
    """알림 설정 조회 테스트"""
    mock_alert_manager.get_thresholds.return_value = {
        'cpu': 80.0,
        'memory': 80.0,
        'disk': 90.0
    }
    
    response = client.get("/alerts/config")
    assert response.status_code == 200
    
    data = response.json()
    assert data['cpu'] == 80.0
    assert data['memory'] == 80.0
    assert data['disk'] == 90.0

def test_update_alert_config(mock_alert_manager):
    """알림 설정 업데이트 테스트"""
    new_config = {
        'cpu': 85.0,
        'memory': 85.0,
        'disk': 95.0
    }
    
    response = client.put("/alerts/config", json=new_config)
    assert response.status_code == 200
    assert response.json() == {"status": "success"}

def test_get_alert_history(mock_alert_manager):
    """알림 기록 조회 테스트"""
    mock_history = [
        {
            'type': 'cpu',
            'value': 95.0,
            'threshold': 80.0,
            'timestamp': datetime.now().isoformat()
        }
    ]
    mock_alert_manager.get_alert_history.return_value = mock_history
    
    response = client.get("/alerts/history")
    assert response.status_code == 200
    
    data = response.json()
    assert len(data) == 1
    assert data[0]['type'] == 'cpu'
    assert data[0]['value'] == 95.0

def test_test_alert(mock_alert_manager):
    """알림 테스트 테스트"""
    response = client.post("/alerts/test")
    assert response.status_code == 200
    assert response.json() == {"status": "test alert sent"}

def test_invalid_alert_config():
    """잘못된 알림 설정 테스트"""
    invalid_config = {
        'cpu': -10.0,
        'memory': 110.0,
        'disk': 200.0
    }
    
    response = client.put("/alerts/config", json=invalid_config)
    assert response.status_code == 400

def test_service_not_found(mock_service_checker):
    """존재하지 않는 서비스 조회 테스트"""
    mock_service_checker.return_value = []
    
    response = client.get("/services/status")
    assert response.status_code == 200
    assert response.json() == []

def test_metrics_collection_error(mock_metrics_collector):
    """메트릭 수집 오류 테스트"""
    mock_metrics_collector.side_effect = Exception("Collection error")
    
    response = client.get("/metrics/system")
    assert response.status_code == 500

def test_alert_history_filtering(mock_alert_manager):
    """알림 기록 필터링 테스트"""
    mock_history = [
        {
            'type': 'cpu',
            'value': 95.0,
            'timestamp': (datetime.now() - timedelta(hours=1)).isoformat()
        },
        {
            'type': 'memory',
            'value': 85.0,
            'timestamp': datetime.now().isoformat()
        }
    ]
    mock_alert_manager.get_alert_history.return_value = mock_history
    
    response = client.get("/alerts/history?type=cpu")
    assert response.status_code == 200
    
    data = response.json()
    assert len(data) == 1
    assert data[0]['type'] == 'cpu'

def test_create_system_metrics(client):
    response = client.post(
        "/metrics/system",
        json={
            "cpu_usage": 45.5,
            "memory_usage": 60.2,
            "disk_usage": 75.8,
            "network_in": 1024.5,
            "network_out": 512.3
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["cpu_usage"] == 45.5
    assert data["memory_usage"] == 60.2
    assert data["disk_usage"] == 75.8

def test_get_system_metrics(client):
    # 테스트 데이터 생성
    client.post(
        "/metrics/system",
        json={
            "cpu_usage": 45.5,
            "memory_usage": 60.2,
            "disk_usage": 75.8,
            "network_in": 1024.5,
            "network_out": 512.3
        }
    )
    
    response = client.get("/metrics/system")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    assert data[0]["cpu_usage"] == 45.5

def test_create_service_status(client):
    response = client.post(
        "/services/status",
        json={
            "service_name": "api-service",
            "is_healthy": True,
            "response_time": 0.5,
            "error_message": None
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["service_name"] == "api-service"
    assert data["is_healthy"] is True

def test_get_service_status(client):
    # 테스트 데이터 생성
    client.post(
        "/services/status",
        json={
            "service_name": "api-service",
            "is_healthy": True,
            "response_time": 0.5,
            "error_message": None
        }
    )
    
    response = client.get("/services/status?service_name=api-service")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    assert data[0]["service_name"] == "api-service"

def test_create_alert_config(client):
    response = client.post(
        "/alerts/config",
        json={
            "alert_type": "test_alert",
            "enabled": True,
            "email_enabled": True,
            "slack_enabled": True,
            "email_recipients": ["test@example.com"],
            "severity": "warning",
            "threshold": 90.0,
            "cooldown_period": 300
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["alert_type"] == "test_alert"
    assert data["enabled"] is True

def test_get_alert_configs(client):
    response = client.get("/alerts/config")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    assert data[0]["alert_type"] == "high_cpu_usage"

def test_create_alert_history(client):
    response = client.post(
        "/alerts/history",
        json={
            "alert_type": "high_cpu_usage",
            "severity": "warning",
            "message": "CPU 사용률이 80%를 초과했습니다",
            "resolved": False
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["alert_type"] == "high_cpu_usage"
    assert data["severity"] == "warning"

def test_resolve_alert(client):
    # 테스트 데이터 생성
    response = client.post(
        "/alerts/history",
        json={
            "alert_type": "high_cpu_usage",
            "severity": "warning",
            "message": "CPU 사용률이 80%를 초과했습니다",
            "resolved": False
        }
    )
    history_id = response.json()["id"]
    
    response = client.put(f"/alerts/history/{history_id}/resolve?resolved_by=admin")
    assert response.status_code == 200
    data = response.json()
    assert data["resolved"] is True
    assert data["resolved_by"] == "admin"

def test_create_service_metrics(client):
    response = client.post(
        "/metrics/service",
        json={
            "service_name": "api-service",
            "request_count": 1000,
            "error_count": 5,
            "avg_response_time": 0.5,
            "max_response_time": 1.2,
            "min_response_time": 0.1
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["service_name"] == "api-service"
    assert data["request_count"] == 1000

def test_create_endpoint(client):
    response = client.post(
        "/endpoints",
        json={
            "service_name": "api-service",
            "endpoint_path": "/api/v1/users",
            "method": "GET",
            "is_monitored": True
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["service_name"] == "api-service"
    assert data["endpoint_path"] == "/api/v1/users"

def test_create_endpoint_metrics(client):
    # 먼저 엔드포인트 생성
    response = client.post(
        "/endpoints",
        json={
            "service_name": "api-service",
            "endpoint_path": "/api/v1/users",
            "method": "GET",
            "is_monitored": True
        }
    )
    endpoint_id = response.json()["id"]
    
    response = client.post(
        "/metrics/endpoint",
        json={
            "endpoint_id": endpoint_id,
            "request_count": 100,
            "error_count": 2,
            "avg_response_time": 0.3,
            "max_response_time": 0.8,
            "min_response_time": 0.1
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["endpoint_id"] == endpoint_id
    assert data["request_count"] == 100

def test_invalid_metrics(client):
    response = client.post(
        "/metrics/system",
        json={
            "cpu_usage": 150.0,  # 유효하지 않은 값
            "memory_usage": 60.2,
            "disk_usage": 75.8,
            "network_in": 1024.5,
            "network_out": 512.3
        }
    )
    assert response.status_code == 422  # 유효성 검사 실패

def test_not_found(client):
    response = client.get("/metrics/system/999")  # 존재하지 않는 ID
    assert response.status_code == 404 
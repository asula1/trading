import pytest
from fastapi.testclient import TestClient
from main import app
import psutil
from datetime import datetime, timedelta

client = TestClient(app)

def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Trading System Monitoring Service"}

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_system_metrics():
    response = client.get("/metrics/system")
    assert response.status_code == 200
    data = response.json()
    assert "cpu_usage" in data
    assert "memory_usage" in data
    assert "disk_usage" in data
    assert "network_traffic" in data
    assert isinstance(data["cpu_usage"], float)
    assert isinstance(data["memory_usage"], float)
    assert isinstance(data["disk_usage"], float)
    assert isinstance(data["network_traffic"], dict)

def test_trading_metrics():
    response = client.get("/metrics/trading")
    assert response.status_code == 200
    data = response.json()
    assert "total_trades" in data
    assert "avg_trade_amount" in data
    assert "completed_trades" in data
    assert "timestamp" in data
    assert isinstance(data["total_trades"], int)
    assert isinstance(data["avg_trade_amount"], (int, float))
    assert isinstance(data["completed_trades"], int)
    assert isinstance(data["timestamp"], str)

def test_services_health():
    response = client.get("/services/health")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    for service in data:
        assert "service_name" in service
        assert "status" in service
        assert "last_check" in service
        assert "details" in service

def test_alerts():
    # 알림 목록 조회
    response = client.get("/alerts")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

    # 알림 해결
    if data:
        alert_id = data[0]["id"]
        response = client.put(f"/alerts/{alert_id}/resolve")
        assert response.status_code == 200
        assert response.json()["message"] == f"Alert {alert_id} resolved"

def test_metrics_collection():
    # 시스템 메트릭 수집 테스트
    cpu_before = psutil.cpu_percent()
    memory_before = psutil.virtual_memory().percent
    disk_before = psutil.disk_usage('/').percent

    # 잠시 대기
    import time
    time.sleep(1)

    cpu_after = psutil.cpu_percent()
    memory_after = psutil.virtual_memory().percent
    disk_after = psutil.disk_usage('/').percent

    # 메트릭이 적절히 수집되었는지 확인
    assert isinstance(cpu_after, float)
    assert isinstance(memory_after, float)
    assert isinstance(disk_after, float)

def test_error_handling():
    # 존재하지 않는 엔드포인트
    response = client.get("/nonexistent")
    assert response.status_code == 404

    # 잘못된 알림 ID
    response = client.put("/alerts/999999/resolve")
    assert response.status_code == 500

def test_service_registration():
    # Consul 서비스 등록 테스트
    response = client.get("/services/health")
    assert response.status_code == 200
    data = response.json()
    monitoring_service = next((s for s in data if s["service_name"] == "monitoring-service"), None)
    assert monitoring_service is not None
    assert monitoring_service["status"] in ["passing", "warning", "critical"] 
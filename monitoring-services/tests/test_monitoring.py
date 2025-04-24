import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import psutil
import consul

from main import app
from metrics_collector import collect_system_metrics, check_service_health
from alert_manager import AlertManager

client = TestClient(app)

@pytest.fixture
def mock_psutil():
    with patch('psutil.cpu_percent') as mock_cpu, \
         patch('psutil.virtual_memory') as mock_memory, \
         patch('psutil.disk_usage') as mock_disk, \
         patch('psutil.net_io_counters') as mock_network:
        
        mock_cpu.return_value = 50.0
        mock_memory.return_value = MagicMock(percent=60.0)
        mock_disk.return_value = MagicMock(percent=70.0)
        mock_network.return_value = MagicMock(bytes_sent=1000, bytes_recv=2000)
        
        yield {
            'cpu': mock_cpu,
            'memory': mock_memory,
            'disk': mock_disk,
            'network': mock_network
        }

@pytest.fixture
def mock_consul():
    with patch('consul.Consul') as mock_consul_class:
        mock_consul = MagicMock()
        mock_consul_class.return_value = mock_consul
        mock_consul.health.service.return_value = [
            {
                'Service': {'ID': 'service1', 'Service': 'test-service'},
                'Checks': [{'Status': 'passing'}]
            }
        ]
        yield mock_consul

def test_api_health():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_system_metrics(mock_psutil):
    response = client.get("/metrics/system")
    assert response.status_code == 200
    data = response.json()
    
    assert "cpu_usage" in data
    assert "memory_usage" in data
    assert "disk_usage" in data
    assert "network_traffic" in data
    
    assert data["cpu_usage"] == 50.0
    assert data["memory_usage"] == 60.0
    assert data["disk_usage"] == 70.0

def test_service_status(mock_consul):
    response = client.get("/services/status")
    assert response.status_code == 200
    data = response.json()
    
    assert isinstance(data, list)
    assert len(data) > 0
    assert data[0]["service_name"] == "test-service"
    assert data[0]["status"] == "healthy"

def test_alert_config():
    # 알림 설정 조회
    response = client.get("/alerts/config")
    assert response.status_code == 200
    config = response.json()
    
    # 알림 설정 업데이트
    new_config = {
        "cpu_threshold": 85,
        "memory_threshold": 90,
        "disk_threshold": 95
    }
    response = client.put("/alerts/config/system", json=new_config)
    assert response.status_code == 200
    
    # 업데이트된 설정 확인
    response = client.get("/alerts/config")
    updated_config = response.json()
    assert updated_config["cpu_threshold"] == 85
    assert updated_config["memory_threshold"] == 90
    assert updated_config["disk_threshold"] == 95

def test_alert_history():
    response = client.get("/alerts/history")
    assert response.status_code == 200
    history = response.json()
    
    assert isinstance(history, list)

def test_alert_test():
    response = client.post("/alerts/test")
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "success"

def test_collect_system_metrics(mock_psutil):
    metrics = collect_system_metrics()
    
    assert metrics["cpu_usage"] == 50.0
    assert metrics["memory_usage"] == 60.0
    assert metrics["disk_usage"] == 70.0
    assert metrics["network_traffic"]["incoming"] == 2000
    assert metrics["network_traffic"]["outgoing"] == 1000

def test_check_service_health(mock_consul):
    services = ["test-service"]
    health_status = check_service_health(services)
    
    assert isinstance(health_status, list)
    assert len(health_status) == 1
    assert health_status[0]["service_name"] == "test-service"
    assert health_status[0]["status"] == "healthy"

def test_alert_manager():
    alert_manager = AlertManager()
    
    # 임계값 초과 테스트
    assert alert_manager.check_threshold("cpu", 90) is True
    assert alert_manager.check_threshold("memory", 95) is True
    assert alert_manager.check_threshold("disk", 98) is True
    
    # 정상 범위 테스트
    assert alert_manager.check_threshold("cpu", 70) is False
    assert alert_manager.check_threshold("memory", 75) is False
    assert alert_manager.check_threshold("disk", 80) is False 
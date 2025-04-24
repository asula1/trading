import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from main import app
from metrics_collector import collect_system_metrics, check_service_health
from alert_manager import AlertManager
from alert_sender import AlertSender

client = TestClient(app)

@pytest.fixture
def mock_system_metrics():
    with patch('psutil.cpu_percent') as mock_cpu, \
         patch('psutil.virtual_memory') as mock_memory, \
         patch('psutil.disk_usage') as mock_disk, \
         patch('psutil.net_io_counters') as mock_network:
        
        mock_cpu.return_value = 50.0
        mock_memory.return_value = MagicMock(
            total=1000000000,
            available=400000000,
            percent=60.0
        )
        mock_disk.return_value = MagicMock(
            total=1000000000,
            used=700000000,
            free=300000000,
            percent=70.0
        )
        mock_network.return_value = MagicMock(
            bytes_sent=1000,
            bytes_recv=2000,
            packets_sent=10,
            packets_recv=20
        )
        yield

@pytest.fixture
def mock_consul():
    with patch('consul.Consul') as mock_consul_class:
        mock_consul = MagicMock()
        mock_consul_class.return_value = mock_consul
        mock_consul.health.service.return_value = [
            {
                'Service': {
                    'ID': 'service1',
                    'Service': 'test-service',
                    'Tags': ['primary']
                },
                'Checks': [
                    {
                        'Status': 'passing',
                        'Output': 'Service is healthy'
                    }
                ]
            }
        ]
        yield mock_consul

@pytest.fixture
def mock_alert_sender():
    with patch('alert_sender.AlertSender') as mock_sender:
        mock_instance = MagicMock()
        mock_sender.return_value = mock_instance
        yield mock_instance

def test_metrics_collection_and_alerting(mock_system_metrics, mock_consul, mock_alert_sender):
    """메트릭 수집 및 알림 통합 테스트"""
    # 메트릭 수집
    metrics = collect_system_metrics()
    assert metrics['cpu_usage'] == 50.0
    assert metrics['memory_usage'] == 60.0
    
    # 서비스 상태 확인
    services = ['test-service']
    health_status = check_service_health(services)
    assert len(health_status) == 1
    assert health_status[0]['status'] == 'healthy'
    
    # 알림 관리자 설정
    alert_manager = AlertManager()
    alert_manager.update_threshold('cpu', 40.0)  # CPU 임계값을 40%로 설정
    
    # 알림 발생 확인
    alert_data = {
        'type': 'cpu',
        'value': 50.0,
        'threshold': 40.0,
        'timestamp': datetime.now()
    }
    alert_manager.process_alert(alert_data)
    
    # 알림 전송 확인
    mock_alert_sender.return_value.send_alert.assert_called_once()

def test_api_and_metrics_integration(mock_system_metrics, mock_consul):
    """API와 메트릭 수집 통합 테스트"""
    # 시스템 메트릭 API 호출
    response = client.get("/metrics/system")
    assert response.status_code == 200
    data = response.json()
    assert data['cpu_usage'] == 50.0
    assert data['memory_usage'] == 60.0
    
    # 서비스 상태 API 호출
    response = client.get("/services/status")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]['service_name'] == 'test-service'

def test_alert_configuration_and_notification(mock_alert_sender):
    """알림 설정 및 전송 통합 테스트"""
    # 알림 설정 업데이트
    new_config = {
        'cpu': 40.0,
        'memory': 70.0,
        'disk': 80.0
    }
    response = client.put("/alerts/config", json=new_config)
    assert response.status_code == 200
    
    # 알림 테스트
    response = client.post("/alerts/test")
    assert response.status_code == 200
    mock_alert_sender.return_value.send_alert.assert_called_once()

def test_metrics_collection_interval():
    """메트릭 수집 간격 통합 테스트"""
    start_time = datetime.now()
    
    # 메트릭 수집 실행
    collect_system_metrics()
    
    # 간격 확인
    end_time = datetime.now()
    assert (end_time - start_time).total_seconds() < 1.0

def test_service_health_monitoring(mock_consul):
    """서비스 상태 모니터링 통합 테스트"""
    # 서비스 상태 확인
    services = ['test-service', 'non-existent-service']
    health_status = check_service_health(services)
    
    # 결과 검증
    assert len(health_status) == 2
    assert any(s['service_name'] == 'test-service' and s['status'] == 'healthy' for s in health_status)
    assert any(s['service_name'] == 'non-existent-service' and s['status'] == 'unknown' for s in health_status)

def test_alert_history_management(mock_alert_sender):
    """알림 기록 관리 통합 테스트"""
    # 알림 발생
    alert_manager = AlertManager()
    alert_data = {
        'type': 'cpu',
        'value': 95.0,
        'threshold': 80.0,
        'timestamp': datetime.now()
    }
    alert_manager.process_alert(alert_data)
    
    # 알림 기록 조회
    response = client.get("/alerts/history")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    assert any(alert['type'] == 'cpu' for alert in data)

def test_error_handling_integration(mock_system_metrics, mock_consul):
    """오류 처리 통합 테스트"""
    # 잘못된 메트릭 요청
    response = client.get("/metrics/invalid")
    assert response.status_code == 404
    
    # 잘못된 알림 설정
    invalid_config = {
        'cpu': -10.0,
        'memory': 110.0
    }
    response = client.put("/alerts/config", json=invalid_config)
    assert response.status_code == 400
    
    # 존재하지 않는 서비스 조회
    response = client.get("/services/status?service=non-existent")
    assert response.status_code == 200
    assert response.json() == []

def test_alert_threshold_management():
    """알림 임계값 관리 통합 테스트"""
    alert_manager = AlertManager()
    
    # 임계값 설정
    alert_manager.update_threshold('cpu', 85.0)
    assert alert_manager.thresholds['cpu'] == 85.0
    
    # 잘못된 임계값 설정 시도
    with pytest.raises(ValueError):
        alert_manager.update_threshold('cpu', -10.0)
    with pytest.raises(ValueError):
        alert_manager.update_threshold('cpu', 110.0)
    
    # 임계값 초과 알림
    alert_data = {
        'type': 'cpu',
        'value': 90.0,
        'threshold': 85.0,
        'timestamp': datetime.now()
    }
    assert alert_manager.check_thresholds('cpu', 90.0) 
import pytest
from unittest.mock import patch, MagicMock
import psutil
from datetime import datetime, timedelta
from metrics_collector import (
    collect_system_metrics,
    check_service_health,
    setup_prometheus_metrics,
    start_metrics_server
)

@pytest.fixture
def mock_psutil():
    with patch('psutil.cpu_percent') as mock_cpu, \
         patch('psutil.virtual_memory') as mock_memory, \
         patch('psutil.disk_usage') as mock_disk, \
         patch('psutil.net_io_counters') as mock_network:
        
        # CPU 사용량 모의
        mock_cpu.return_value = 50.0
        
        # 메모리 사용량 모의
        mock_memory.return_value = MagicMock(
            total=1000000000,
            available=400000000,
            percent=60.0
        )
        
        # 디스크 사용량 모의
        mock_disk.return_value = MagicMock(
            total=1000000000,
            used=700000000,
            free=300000000,
            percent=70.0
        )
        
        # 네트워크 트래픽 모의
        mock_network.return_value = MagicMock(
            bytes_sent=1000,
            bytes_recv=2000,
            packets_sent=10,
            packets_recv=20
        )
        
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
        
        # Consul 서비스 상태 모의
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

def test_collect_system_metrics(mock_psutil):
    metrics = collect_system_metrics()
    
    assert metrics['cpu_usage'] == 50.0
    assert metrics['memory_usage'] == 60.0
    assert metrics['disk_usage'] == 70.0
    assert metrics['network_traffic']['incoming'] == 2000
    assert metrics['network_traffic']['outgoing'] == 1000

def test_check_service_health(mock_consul):
    services = ['test-service']
    health_status = check_service_health(services)
    
    assert len(health_status) == 1
    assert health_status[0]['service_name'] == 'test-service'
    assert health_status[0]['status'] == 'healthy'
    assert health_status[0]['tags'] == ['primary']

def test_prometheus_metrics():
    metrics = setup_prometheus_metrics()
    
    assert metrics['cpu_usage']._type == 'gauge'
    assert metrics['memory_usage']._type == 'gauge'
    assert metrics['disk_usage']._type == 'gauge'
    assert metrics['network_traffic_in']._type == 'counter'
    assert metrics['network_traffic_out']._type == 'counter'
    assert metrics['service_health']._type == 'gauge'

def test_metrics_collection_interval(mock_psutil):
    """메트릭 수집 간격 테스트"""
    start_time = datetime.now()
    collect_system_metrics()
    end_time = datetime.now()
    
    assert (end_time - start_time).total_seconds() < 1.0

def test_network_traffic_calculation(mock_psutil):
    """네트워크 트래픽 계산 테스트"""
    metrics = collect_system_metrics()
    
    assert metrics['network_traffic']['incoming'] == 2000
    assert metrics['network_traffic']['outgoing'] == 1000
    assert metrics['network_traffic']['packets_in'] == 20
    assert metrics['network_traffic']['packets_out'] == 10

def test_disk_usage_calculation(mock_psutil):
    """디스크 사용량 계산 테스트"""
    metrics = collect_system_metrics()
    
    assert metrics['disk_usage'] == 70.0
    assert metrics['disk_total'] == 1000000000
    assert metrics['disk_used'] == 700000000
    assert metrics['disk_free'] == 300000000

def test_memory_usage_calculation(mock_psutil):
    """메모리 사용량 계산 테스트"""
    metrics = collect_system_metrics()
    
    assert metrics['memory_usage'] == 60.0
    assert metrics['memory_total'] == 1000000000
    assert metrics['memory_available'] == 400000000
    assert metrics['memory_used'] == 600000000

def test_service_health_status(mock_consul):
    """서비스 상태 확인 테스트"""
    services = ['test-service', 'non-existent-service']
    health_status = check_service_health(services)
    
    assert len(health_status) == 2
    assert any(s['service_name'] == 'test-service' and s['status'] == 'healthy' for s in health_status)
    assert any(s['service_name'] == 'non-existent-service' and s['status'] == 'unknown' for s in health_status)

def test_metrics_server_start():
    """메트릭 서버 시작 테스트"""
    with patch('http.server.HTTPServer') as mock_server:
        start_metrics_server('localhost', 8000)
        mock_server.assert_called_once() 
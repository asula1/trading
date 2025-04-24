import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from alert_manager import AlertManager

@pytest.fixture
def alert_manager():
    return AlertManager()

@pytest.fixture
def mock_alert_sender():
    with patch('alert_sender.AlertSender') as mock_sender:
        mock_sender.return_value = MagicMock()
        yield mock_sender

def test_check_thresholds(alert_manager):
    """임계값 체크 테스트"""
    # 정상 범위
    assert not alert_manager.check_thresholds('cpu', 50.0)
    assert not alert_manager.check_thresholds('memory', 60.0)
    assert not alert_manager.check_thresholds('disk', 70.0)
    
    # 임계값 초과
    assert alert_manager.check_thresholds('cpu', 90.0)
    assert alert_manager.check_thresholds('memory', 85.0)
    assert alert_manager.check_thresholds('disk', 95.0)

def test_process_alert(alert_manager, mock_alert_sender):
    """알림 처리 테스트"""
    alert_data = {
        'type': 'cpu',
        'value': 95.0,
        'threshold': 80.0,
        'timestamp': datetime.now()
    }
    
    alert_manager.process_alert(alert_data)
    
    # 알림 기록 확인
    assert len(alert_manager.alert_history) == 1
    assert alert_manager.alert_history[0]['type'] == 'cpu'
    assert alert_manager.alert_history[0]['value'] == 95.0

def test_cleanup_old_alerts(alert_manager):
    """오래된 알림 정리 테스트"""
    # 오래된 알림 추가
    old_alert = {
        'type': 'cpu',
        'value': 95.0,
        'timestamp': datetime.now() - timedelta(hours=2)
    }
    alert_manager.alert_history.append(old_alert)
    
    # 새로운 알림 추가
    new_alert = {
        'type': 'memory',
        'value': 85.0,
        'timestamp': datetime.now()
    }
    alert_manager.alert_history.append(new_alert)
    
    # 정리 실행
    alert_manager.cleanup_old_alerts()
    
    # 오래된 알림이 제거되었는지 확인
    assert len(alert_manager.alert_history) == 1
    assert alert_manager.alert_history[0]['type'] == 'memory'

def test_duplicate_alert_prevention(alert_manager):
    """중복 알림 방지 테스트"""
    alert_data = {
        'type': 'cpu',
        'value': 95.0,
        'threshold': 80.0,
        'timestamp': datetime.now()
    }
    
    # 첫 번째 알림
    alert_manager.process_alert(alert_data)
    
    # 동일한 알림 다시 발생
    alert_manager.process_alert(alert_data)
    
    # 중복 알림이 방지되었는지 확인
    assert len(alert_manager.alert_history) == 1

def test_alert_cooldown(alert_manager):
    """알림 쿨다운 테스트"""
    alert_data = {
        'type': 'cpu',
        'value': 95.0,
        'threshold': 80.0,
        'timestamp': datetime.now()
    }
    
    # 첫 번째 알림
    alert_manager.process_alert(alert_data)
    
    # 쿨다운 기간 내에 동일한 알림 발생
    alert_data['timestamp'] = datetime.now() + timedelta(minutes=30)
    alert_manager.process_alert(alert_data)
    
    # 쿨다운 기간이 지난 후 알림 발생
    alert_data['timestamp'] = datetime.now() + timedelta(hours=2)
    alert_manager.process_alert(alert_data)
    
    # 쿨다운이 적용되었는지 확인
    assert len(alert_manager.alert_history) == 2

def test_alert_threshold_configuration(alert_manager):
    """알림 임계값 설정 테스트"""
    # 기본 임계값 확인
    assert alert_manager.thresholds['cpu'] == 80.0
    assert alert_manager.thresholds['memory'] == 80.0
    assert alert_manager.thresholds['disk'] == 90.0
    
    # 임계값 변경
    alert_manager.update_threshold('cpu', 85.0)
    assert alert_manager.thresholds['cpu'] == 85.0
    
    # 잘못된 임계값 설정 시도
    with pytest.raises(ValueError):
        alert_manager.update_threshold('cpu', -10.0)
    with pytest.raises(ValueError):
        alert_manager.update_threshold('cpu', 110.0)

def test_alert_notification_channels(alert_manager, mock_alert_sender):
    """알림 채널 테스트"""
    alert_data = {
        'type': 'cpu',
        'value': 95.0,
        'threshold': 80.0,
        'timestamp': datetime.now()
    }
    
    # 이메일 알림 테스트
    alert_manager.process_alert(alert_data, channel='email')
    mock_alert_sender.return_value.send_email.assert_called_once()
    
    # Slack 알림 테스트
    alert_manager.process_alert(alert_data, channel='slack')
    mock_alert_sender.return_value.send_slack.assert_called_once()

def test_alert_message_formatting(alert_manager):
    """알림 메시지 포맷팅 테스트"""
    alert_data = {
        'type': 'cpu',
        'value': 95.0,
        'threshold': 80.0,
        'timestamp': datetime.now()
    }
    
    message = alert_manager.format_alert_message(alert_data)
    
    assert 'CPU 사용량' in message
    assert '95.0%' in message
    assert '임계값: 80.0%' in message
    assert str(alert_data['timestamp']) in message 
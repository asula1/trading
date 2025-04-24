from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
import psutil
import logging
from datetime import datetime, timedelta
from .metrics_collector import collect_system_metrics, check_service_health
from .alert_manager import AlertManager

# 로깅 설정
logging.config.fileConfig('logging.conf')
logger = logging.getLogger('monitoring')

app = FastAPI(title="Trading System Monitoring API")

# 데이터 모델 정의
class SystemMetrics(BaseModel):
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    network_in: float
    network_out: float
    timestamp: datetime

class ServiceStatus(BaseModel):
    service_name: str
    status: str
    last_check: datetime
    details: Optional[dict] = None

class AlertConfig(BaseModel):
    alert_type: str
    threshold: float
    enabled: bool

class AlertHistory(BaseModel):
    alert_type: str
    message: str
    timestamp: datetime
    resolved: bool

# API 엔드포인트
@app.get("/")
async def root():
    """API 상태 확인"""
    return {"status": "healthy", "version": "1.0.0"}

@app.get("/metrics/system", response_model=SystemMetrics)
async def get_system_metrics():
    """시스템 메트릭 조회"""
    try:
        metrics = collect_system_metrics()
        return SystemMetrics(
            cpu_usage=metrics['cpu'],
            memory_usage=metrics['memory'],
            disk_usage=metrics['disk'],
            network_in=metrics['network_in'],
            network_out=metrics['network_out'],
            timestamp=datetime.now()
        )
    except Exception as e:
        logger.error(f"시스템 메트릭 조회 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/services/status", response_model=List[ServiceStatus])
async def get_services_status():
    """서비스 상태 조회"""
    try:
        services = check_service_health()
        return [
            ServiceStatus(
                service_name=service['name'],
                status=service['status'],
                last_check=service['last_check'],
                details=service.get('details')
            )
            for service in services
        ]
    except Exception as e:
        logger.error(f"서비스 상태 조회 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/alerts/config", response_model=List[AlertConfig])
async def get_alert_config():
    """알림 설정 조회"""
    try:
        alert_manager = AlertManager()
        return [
            AlertConfig(
                alert_type=alert_type,
                threshold=threshold,
                enabled=True
            )
            for alert_type, threshold in alert_manager.thresholds.items()
        ]
    except Exception as e:
        logger.error(f"알림 설정 조회 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/alerts/config/{alert_type}")
async def update_alert_config(alert_type: str, config: AlertConfig):
    """알림 설정 업데이트"""
    try:
        alert_manager = AlertManager()
        if alert_type not in alert_manager.thresholds:
            raise HTTPException(status_code=404, detail="알림 유형을 찾을 수 없습니다.")
        
        alert_manager.thresholds[alert_type] = config.threshold
        return {"message": "알림 설정이 업데이트되었습니다."}
    except Exception as e:
        logger.error(f"알림 설정 업데이트 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/alerts/history", response_model=List[AlertHistory])
async def get_alert_history(hours: int = 24):
    """알림 이력 조회"""
    try:
        alert_manager = AlertManager()
        history = []
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        for key, timestamp in alert_manager.alert_history.items():
            if timestamp >= cutoff_time:
                alert_type = key.split('_')[0]
                history.append(
                    AlertHistory(
                        alert_type=alert_type,
                        message=f"{alert_type.upper()} 사용량 초과 알림",
                        timestamp=timestamp,
                        resolved=False
                    )
                )
        
        return history
    except Exception as e:
        logger.error(f"알림 이력 조회 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/alerts/test")
async def test_alert(background_tasks: BackgroundTasks):
    """알림 테스트"""
    try:
        alert_manager = AlertManager()
        test_metrics = {
            'cpu': 95,
            'memory': 90,
            'disk': 95
        }
        
        background_tasks.add_task(alert_manager.process_alerts, test_metrics)
        return {"message": "테스트 알림이 전송되었습니다."}
    except Exception as e:
        logger.error(f"알림 테스트 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8090) 
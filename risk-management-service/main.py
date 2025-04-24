from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
from dotenv import load_dotenv
import logging
from prometheus_client import Counter, Histogram, start_http_server
import consul
import jaeger_client
from opentracing.ext import tags
from opentracing.propagation import Format
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime, timedelta
import pika
import json
from typing import List, Dict, Optional
import requests
import numpy as np
import pandas as pd
from scipy import stats

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Prometheus 메트릭
risk_requests = Counter('risk_requests_total', 'Total risk assessment requests')
risk_latency = Histogram('risk_latency_seconds', 'Risk assessment latency')

# Jaeger 설정
config = jaeger_client.Config(
    config={
        'sampler': {
            'type': 'const',
            'param': 1,
        },
        'logging': True,
    },
    service_name='risk-management-service'
)
tracer = config.initialize_tracer()

# 데이터베이스 설정
DATABASE_URL = "postgresql://trading:trading123@postgres:5432/trading_db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 모델 정의
class RiskProfile(Base):
    __tablename__ = "risk_profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    max_drawdown = Column(Float)  # 최대 손실 허용치
    max_position_size = Column(Float)  # 최대 포지션 크기
    max_leverage = Column(Float)  # 최대 레버리지
    risk_per_trade = Column(Float)  # 거래당 위험 비율
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class RiskAlert(Base):
    __tablename__ = "risk_alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    alert_type = Column(String)  # drawdown, leverage, position_size, etc.
    severity = Column(String)  # low, medium, high
    message = Column(String)
    metadata = Column(JSON)  # 추가 데이터
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

class RiskMetrics(Base):
    __tablename__ = "risk_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    var_95 = Column(Float)  # 95% VaR
    var_99 = Column(Float)  # 99% VaR
    expected_shortfall = Column(Float)  # Expected Shortfall
    sharpe_ratio = Column(Float)  # Sharpe Ratio
    sortino_ratio = Column(Float)  # Sortino Ratio
    max_drawdown = Column(Float)  # 최대 손실폭
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

app = FastAPI()

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Consul 클라이언트 설정
consul_client = consul.Consul(host='consul', port=8500)

# RabbitMQ 설정
RABBITMQ_HOST = 'rabbitmq'
RABBITMQ_PORT = 5672

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def calculate_var(returns: List[float], confidence_level: float = 0.95) -> float:
    """Value at Risk 계산"""
    return np.percentile(returns, (1 - confidence_level) * 100)

def calculate_expected_shortfall(returns: List[float], confidence_level: float = 0.95) -> float:
    """Expected Shortfall 계산"""
    var = calculate_var(returns, confidence_level)
    return np.mean([r for r in returns if r <= var])

def calculate_sharpe_ratio(returns: List[float], risk_free_rate: float = 0.0) -> float:
    """Sharpe Ratio 계산"""
    excess_returns = np.array(returns) - risk_free_rate
    return np.mean(excess_returns) / np.std(excess_returns)

def calculate_sortino_ratio(returns: List[float], risk_free_rate: float = 0.0) -> float:
    """Sortino Ratio 계산"""
    excess_returns = np.array(returns) - risk_free_rate
    downside_returns = excess_returns[excess_returns < 0]
    if len(downside_returns) == 0:
        return 0
    return np.mean(excess_returns) / np.std(downside_returns)

def calculate_max_drawdown(returns: List[float]) -> float:
    """최대 손실폭 계산"""
    cumulative = np.cumprod(1 + np.array(returns))
    running_max = np.maximum.accumulate(cumulative)
    drawdown = (cumulative - running_max) / running_max
    return np.min(drawdown)

def publish_risk_alert(alert: RiskAlert):
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=RABBITMQ_HOST, port=RABBITMQ_PORT)
        )
        channel = connection.channel()
        channel.exchange_declare(exchange='risk_alerts', exchange_type='fanout')
        
        message = {
            'alert_id': alert.id,
            'user_id': alert.user_id,
            'alert_type': alert.alert_type,
            'severity': alert.severity,
            'message': alert.message,
            'metadata': alert.metadata,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        channel.basic_publish(
            exchange='risk_alerts',
            routing_key='',
            body=json.dumps(message)
        )
        connection.close()
    except Exception as e:
        logger.error(f"Error publishing risk alert: {str(e)}")

@app.on_event("startup")
async def startup_event():
    # Consul에 서비스 등록
    consul_client.agent.service.register(
        name='risk-management-service',
        service_id='risk-management-service-1',
        address='risk-management-service',
        port=8085,
        check=consul.Check.http(
            url='http://risk-management-service:8085/health',
            interval='10s',
            timeout='5s'
        )
    )
    # Prometheus 메트릭 서버 시작
    start_http_server(8000)

@app.get("/")
async def root():
    return {"message": "Risk Management Service"}

@app.post("/risk-profiles")
async def create_risk_profile(
    user_id: int,
    max_drawdown: float,
    max_position_size: float,
    max_leverage: float,
    risk_per_trade: float,
    db: SessionLocal = Depends(get_db)
):
    with tracer.start_span('create_risk_profile') as span:
        span.set_tag(tags.HTTP_METHOD, 'POST')
        span.set_tag(tags.HTTP_URL, '/risk-profiles')
        
        try:
            profile = RiskProfile(
                user_id=user_id,
                max_drawdown=max_drawdown,
                max_position_size=max_position_size,
                max_leverage=max_leverage,
                risk_per_trade=risk_per_trade
            )
            db.add(profile)
            db.commit()
            db.refresh(profile)
            return profile
        except Exception as e:
            logger.error(f"Error creating risk profile: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to create risk profile")

@app.get("/risk-profiles/{user_id}")
async def get_risk_profile(user_id: int, db: SessionLocal = Depends(get_db)):
    with tracer.start_span('get_risk_profile') as span:
        span.set_tag(tags.HTTP_METHOD, 'GET')
        span.set_tag(tags.HTTP_URL, f'/risk-profiles/{user_id}')
        
        try:
            profile = db.query(RiskProfile).filter(RiskProfile.user_id == user_id).first()
            if not profile:
                raise HTTPException(status_code=404, detail="Risk profile not found")
            return profile
        except Exception as e:
            logger.error(f"Error fetching risk profile: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch risk profile")

@app.post("/risk-assessment")
async def assess_risk(
    user_id: int,
    db: SessionLocal = Depends(get_db)
):
    with tracer.start_span('assess_risk') as span:
        span.set_tag(tags.HTTP_METHOD, 'POST')
        span.set_tag(tags.HTTP_URL, '/risk-assessment')
        
        risk_requests.inc()
        start_time = time.time()
        
        try:
            # 사용자의 포지션 정보 가져오기
            response = requests.get(f"http://position-service:8084/positions/{user_id}")
            positions = response.json()
            
            # 사용자의 리스크 프로필 가져오기
            profile = db.query(RiskProfile).filter(RiskProfile.user_id == user_id).first()
            if not profile:
                raise HTTPException(status_code=404, detail="Risk profile not found")
            
            # 리스크 메트릭 계산
            returns = []
            total_exposure = 0.0
            max_leverage_used = 0.0
            
            for position in positions:
                # 수익률 계산
                if position['side'] == 'long':
                    returns.append((position['current_price'] - position['entry_price']) / position['entry_price'])
                else:  # short
                    returns.append((position['entry_price'] - position['current_price']) / position['entry_price'])
                
                # 총 노출 계산
                exposure = position['quantity'] * position['current_price']
                total_exposure += exposure
                
                # 최대 레버리지 계산
                leverage = exposure / position['margin']
                max_leverage_used = max(max_leverage_used, leverage)
            
            # 리스크 메트릭 저장
            metrics = RiskMetrics(
                user_id=user_id,
                var_95=calculate_var(returns, 0.95),
                var_99=calculate_var(returns, 0.99),
                expected_shortfall=calculate_expected_shortfall(returns, 0.95),
                sharpe_ratio=calculate_sharpe_ratio(returns),
                sortino_ratio=calculate_sortino_ratio(returns),
                max_drawdown=calculate_max_drawdown(returns)
            )
            db.add(metrics)
            db.commit()
            
            # 리스크 알림 생성
            alerts = []
            
            # 최대 손실폭 체크
            if metrics.max_drawdown < -profile.max_drawdown:
                alert = RiskAlert(
                    user_id=user_id,
                    alert_type='drawdown',
                    severity='high',
                    message=f"Maximum drawdown exceeded: {metrics.max_drawdown:.2%}",
                    metadata={'max_drawdown': metrics.max_drawdown}
                )
                db.add(alert)
                alerts.append(alert)
            
            # 레버리지 체크
            if max_leverage_used > profile.max_leverage:
                alert = RiskAlert(
                    user_id=user_id,
                    alert_type='leverage',
                    severity='high',
                    message=f"Maximum leverage exceeded: {max_leverage_used:.2f}x",
                    metadata={'leverage': max_leverage_used}
                )
                db.add(alert)
                alerts.append(alert)
            
            # 포지션 크기 체크
            if total_exposure > profile.max_position_size:
                alert = RiskAlert(
                    user_id=user_id,
                    alert_type='position_size',
                    severity='high',
                    message=f"Maximum position size exceeded: {total_exposure:.2f}",
                    metadata={'position_size': total_exposure}
                )
                db.add(alert)
                alerts.append(alert)
            
            db.commit()
            
            # 알림 발행
            for alert in alerts:
                publish_risk_alert(alert)
            
            risk_latency.observe(time.time() - start_time)
            return {
                'metrics': metrics,
                'alerts': alerts
            }
        except Exception as e:
            logger.error(f"Error assessing risk: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to assess risk")

@app.get("/risk-alerts/{user_id}")
async def get_risk_alerts(
    user_id: int,
    resolved: Optional[bool] = None,
    db: SessionLocal = Depends(get_db)
):
    with tracer.start_span('get_risk_alerts') as span:
        span.set_tag(tags.HTTP_METHOD, 'GET')
        span.set_tag(tags.HTTP_URL, f'/risk-alerts/{user_id}')
        
        try:
            query = db.query(RiskAlert).filter(RiskAlert.user_id == user_id)
            if resolved is not None:
                if resolved:
                    query = query.filter(RiskAlert.resolved_at.isnot(None))
                else:
                    query = query.filter(RiskAlert.resolved_at.is_(None))
            alerts = query.order_by(RiskAlert.created_at.desc()).all()
            return alerts
        except Exception as e:
            logger.error(f"Error fetching risk alerts: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch risk alerts")

@app.put("/risk-alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: int, db: SessionLocal = Depends(get_db)):
    with tracer.start_span('resolve_alert') as span:
        span.set_tag(tags.HTTP_METHOD, 'PUT')
        span.set_tag(tags.HTTP_URL, f'/risk-alerts/{alert_id}/resolve')
        
        try:
            alert = db.query(RiskAlert).filter(RiskAlert.id == alert_id).first()
            if not alert:
                raise HTTPException(status_code=404, detail="Alert not found")
            
            alert.resolved_at = datetime.utcnow()
            db.commit()
            return alert
        except Exception as e:
            logger.error(f"Error resolving alert: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to resolve alert")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8085) 
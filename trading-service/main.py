from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
from dotenv import load_dotenv
import requests
import json
import time
import jwt
import hashlib
import hmac
import base64
import logging
from prometheus_client import Counter, Histogram, start_http_server
import consul
import jaeger_client
from opentracing.ext import tags
from opentracing.propagation import Format
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import pika
import asyncio
from typing import List, Dict, Optional

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Prometheus 메트릭
trade_requests = Counter('trade_requests_total', 'Total trade requests')
trade_latency = Histogram('trade_latency_seconds', 'Trade request latency')

# Jaeger 설정
config = jaeger_client.Config(
    config={
        'sampler': {
            'type': 'const',
            'param': 1,
        },
        'logging': True,
    },
    service_name='trading-service'
)
tracer = config.initialize_tracer()

# 데이터베이스 설정
DATABASE_URL = "postgresql://trading:trading123@postgres:5432/trading_db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 모델 정의
class Trade(Base):
    __tablename__ = "trades"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    side = Column(String)  # buy or sell
    price = Column(Float)
    quantity = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)
    status = Column(String)  # pending, completed, failed

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

# Upbit API 설정
UPBIT_API_URL = "https://api.upbit.com/v1"
UPBIT_ACCESS_KEY = os.getenv("UPBIT_ACCESS_KEY")
UPBIT_SECRET_KEY = os.getenv("UPBIT_SECRET_KEY")

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

def create_jwt_token(payload: dict) -> str:
    return jwt.encode(payload, UPBIT_SECRET_KEY, algorithm='HS512')

def get_upbit_signature(query_string: str) -> str:
    m = hmac.new(UPBIT_SECRET_KEY.encode(), query_string.encode(), hashlib.sha512)
    return base64.b64encode(m.digest()).decode()

@app.on_event("startup")
async def startup_event():
    # Consul에 서비스 등록
    consul_client.agent.service.register(
        name='trading-service',
        service_id='trading-service-1',
        address='trading-service',
        port=8081,
        check=consul.Check.http(
            url='http://trading-service:8081/health',
            interval='10s',
            timeout='5s'
        )
    )
    # Prometheus 메트릭 서버 시작
    start_http_server(8000)

@app.get("/")
async def root():
    return {"message": "Trading Service"}

@app.get("/portfolio")
async def get_portfolio():
    with tracer.start_span('get_portfolio') as span:
        span.set_tag(tags.HTTP_METHOD, 'GET')
        span.set_tag(tags.HTTP_URL, '/portfolio')
        
        try:
            # Upbit API 호출을 위한 JWT 토큰 생성
            payload = {
                'access_key': UPBIT_ACCESS_KEY,
                'nonce': str(int(time.time() * 1000))
            }
            jwt_token = create_jwt_token(payload)
            
            # API 호출
            headers = {'Authorization': f'Bearer {jwt_token}'}
            response = requests.get(f"{UPBIT_API_URL}/accounts", headers=headers)
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching portfolio: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch portfolio")

@app.post("/trade")
async def execute_trade(symbol: str, side: str, quantity: float, db: SessionLocal = Depends(get_db)):
    with tracer.start_span('execute_trade') as span:
        span.set_tag(tags.HTTP_METHOD, 'POST')
        span.set_tag(tags.HTTP_URL, '/trade')
        span.set_tag('trade.symbol', symbol)
        span.set_tag('trade.side', side)
        span.set_tag('trade.quantity', quantity)
        
        trade_requests.inc()
        start_time = time.time()
        
        try:
            # 거래 기록 생성
            trade = Trade(
                symbol=symbol,
                side=side,
                quantity=quantity,
                status='pending'
            )
            db.add(trade)
            db.commit()
            
            # Upbit API 호출을 위한 JWT 토큰 생성
            query = {
                'market': f'KRW-{symbol}',
                'side': side,
                'volume': str(quantity),
                'ord_type': 'market'
            }
            query_string = '&'.join([f"{k}={v}" for k, v in query.items()])
            
            payload = {
                'access_key': UPBIT_ACCESS_KEY,
                'nonce': str(int(time.time() * 1000)),
                'query_hash': hashlib.sha512(query_string.encode()).hexdigest(),
                'query_hash_alg': 'SHA512'
            }
            jwt_token = create_jwt_token(payload)
            
            # API 호출
            headers = {'Authorization': f'Bearer {jwt_token}'}
            response = requests.post(f"{UPBIT_API_URL}/orders", headers=headers, data=query)
            
            if response.status_code == 201:
                trade.status = 'completed'
                trade.price = float(response.json()['price'])
            else:
                trade.status = 'failed'
            
            db.commit()
            
            trade_latency.observe(time.time() - start_time)
            return response.json()
        except Exception as e:
            logger.error(f"Error executing trade: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to execute trade")

@app.get("/history")
async def get_trade_history(db: SessionLocal = Depends(get_db)):
    with tracer.start_span('get_trade_history') as span:
        span.set_tag(tags.HTTP_METHOD, 'GET')
        span.set_tag(tags.HTTP_URL, '/history')
        
        try:
            trades = db.query(Trade).order_by(Trade.timestamp.desc()).all()
            return trades
        except Exception as e:
            logger.error(f"Error fetching trade history: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch trade history")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8081) 
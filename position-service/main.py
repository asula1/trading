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
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import pika
import json
from typing import List, Dict, Optional
import requests

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Prometheus 메트릭
position_requests = Counter('position_requests_total', 'Total position requests')
position_latency = Histogram('position_latency_seconds', 'Position request latency')

# Jaeger 설정
config = jaeger_client.Config(
    config={
        'sampler': {
            'type': 'const',
            'param': 1,
        },
        'logging': True,
    },
    service_name='position-service'
)
tracer = config.initialize_tracer()

# 데이터베이스 설정
DATABASE_URL = "postgresql://trading:trading123@postgres:5432/trading_db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 모델 정의
class Position(Base):
    __tablename__ = "positions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    symbol = Column(String, index=True)
    side = Column(String)  # long or short
    entry_price = Column(Float)
    current_price = Column(Float)
    quantity = Column(Float)
    leverage = Column(Float, default=1.0)
    margin = Column(Float)
    unrealized_pnl = Column(Float)
    realized_pnl = Column(Float, default=0.0)
    status = Column(String)  # open, closed, liquidated
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PositionHistory(Base):
    __tablename__ = "position_history"
    
    id = Column(Integer, primary_key=True, index=True)
    position_id = Column(Integer, ForeignKey('positions.id'))
    event_type = Column(String)  # open, close, update, liquidate
    price = Column(Float)
    quantity = Column(Float)
    pnl = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)
    metadata = Column(String)  # JSON string for additional data

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

def update_position_pnl(position: Position, current_price: float):
    if position.side == "long":
        position.unrealized_pnl = (current_price - position.entry_price) * position.quantity
    else:  # short
        position.unrealized_pnl = (position.entry_price - current_price) * position.quantity
    return position

def publish_position_update(position: Position):
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=RABBITMQ_HOST, port=RABBITMQ_PORT)
        )
        channel = connection.channel()
        channel.exchange_declare(exchange='position_updates', exchange_type='fanout')
        
        message = {
            'position_id': position.id,
            'user_id': position.user_id,
            'symbol': position.symbol,
            'side': position.side,
            'current_price': position.current_price,
            'unrealized_pnl': position.unrealized_pnl,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        channel.basic_publish(
            exchange='position_updates',
            routing_key='',
            body=json.dumps(message)
        )
        connection.close()
    except Exception as e:
        logger.error(f"Error publishing position update: {str(e)}")

@app.on_event("startup")
async def startup_event():
    # Consul에 서비스 등록
    consul_client.agent.service.register(
        name='position-service',
        service_id='position-service-1',
        address='position-service',
        port=8084,
        check=consul.Check.http(
            url='http://position-service:8084/health',
            interval='10s',
            timeout='5s'
        )
    )
    # Prometheus 메트릭 서버 시작
    start_http_server(8000)

@app.get("/")
async def root():
    return {"message": "Position Service"}

@app.post("/positions")
async def create_position(
    user_id: int,
    symbol: str,
    side: str,
    entry_price: float,
    quantity: float,
    leverage: float = 1.0,
    db: SessionLocal = Depends(get_db)
):
    with tracer.start_span('create_position') as span:
        span.set_tag(tags.HTTP_METHOD, 'POST')
        span.set_tag(tags.HTTP_URL, '/positions')
        
        position_requests.inc()
        start_time = time.time()
        
        try:
            # 현재 가격 가져오기
            response = requests.get(f"http://market-data-service:8080/coin/{symbol}")
            current_price = float(response.json()['trade_price'])
            
            # 포지션 생성
            margin = (entry_price * quantity) / leverage
            position = Position(
                user_id=user_id,
                symbol=symbol,
                side=side,
                entry_price=entry_price,
                current_price=current_price,
                quantity=quantity,
                leverage=leverage,
                margin=margin,
                status='open'
            )
            position = update_position_pnl(position, current_price)
            
            db.add(position)
            db.commit()
            db.refresh(position)
            
            # 포지션 히스토리 기록
            history = PositionHistory(
                position_id=position.id,
                event_type='open',
                price=entry_price,
                quantity=quantity,
                pnl=0.0
            )
            db.add(history)
            db.commit()
            
            # 포지션 업데이트 발행
            publish_position_update(position)
            
            position_latency.observe(time.time() - start_time)
            return position
        except Exception as e:
            logger.error(f"Error creating position: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to create position")

@app.get("/positions/{user_id}")
async def get_user_positions(user_id: int, db: SessionLocal = Depends(get_db)):
    with tracer.start_span('get_user_positions') as span:
        span.set_tag(tags.HTTP_METHOD, 'GET')
        span.set_tag(tags.HTTP_URL, f'/positions/{user_id}')
        
        try:
            positions = db.query(Position).filter(
                Position.user_id == user_id,
                Position.status == 'open'
            ).all()
            
            # 현재 가격 업데이트
            for position in positions:
                response = requests.get(f"http://market-data-service:8080/coin/{position.symbol}")
                current_price = float(response.json()['trade_price'])
                position.current_price = current_price
                position = update_position_pnl(position, current_price)
            
            db.commit()
            return positions
        except Exception as e:
            logger.error(f"Error fetching positions: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch positions")

@app.put("/positions/{position_id}/close")
async def close_position(
    position_id: int,
    close_price: Optional[float] = None,
    db: SessionLocal = Depends(get_db)
):
    with tracer.start_span('close_position') as span:
        span.set_tag(tags.HTTP_METHOD, 'PUT')
        span.set_tag(tags.HTTP_URL, f'/positions/{position_id}/close')
        
        try:
            position = db.query(Position).filter(Position.id == position_id).first()
            if not position:
                raise HTTPException(status_code=404, detail="Position not found")
            
            if position.status != 'open':
                raise HTTPException(status_code=400, detail="Position is not open")
            
            # 종가 가져오기
            if close_price is None:
                response = requests.get(f"http://market-data-service:8080/coin/{position.symbol}")
                close_price = float(response.json()['trade_price'])
            
            # 포지션 종료
            position.status = 'closed'
            position.current_price = close_price
            position = update_position_pnl(position, close_price)
            position.realized_pnl = position.unrealized_pnl
            
            # 포지션 히스토리 기록
            history = PositionHistory(
                position_id=position.id,
                event_type='close',
                price=close_price,
                quantity=position.quantity,
                pnl=position.realized_pnl
            )
            db.add(history)
            db.commit()
            
            # 포지션 업데이트 발행
            publish_position_update(position)
            
            return position
        except Exception as e:
            logger.error(f"Error closing position: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to close position")

@app.get("/positions/{position_id}/history")
async def get_position_history(position_id: int, db: SessionLocal = Depends(get_db)):
    with tracer.start_span('get_position_history') as span:
        span.set_tag(tags.HTTP_METHOD, 'GET')
        span.set_tag(tags.HTTP_URL, f'/positions/{position_id}/history')
        
        try:
            history = db.query(PositionHistory).filter(
                PositionHistory.position_id == position_id
            ).order_by(PositionHistory.timestamp.desc()).all()
            return history
        except Exception as e:
            logger.error(f"Error fetching position history: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch position history")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8084) 
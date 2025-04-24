from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
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
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, JSON, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime, timedelta
import pika
import json
from typing import List, Dict, Optional
import requests
import numpy as np
import pandas as pd
import backtrader as bt
import matplotlib.pyplot as plt
import io
import base64
from concurrent.futures import ThreadPoolExecutor
import asyncio

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Prometheus 메트릭
backtest_requests = Counter('backtest_requests_total', 'Total backtest requests')
backtest_latency = Histogram('backtest_latency_seconds', 'Backtest execution latency')

# Jaeger 설정
config = jaeger_client.Config(
    config={
        'sampler': {
            'type': 'const',
            'param': 1,
        },
        'logging': True,
    },
    service_name='backtesting-service'
)
tracer = config.initialize_tracer()

# 데이터베이스 설정
DATABASE_URL = "postgresql://trading:trading123@postgres:5432/trading_db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 모델 정의
class Backtest(Base):
    __tablename__ = "backtests"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    strategy_name = Column(String)
    symbol = Column(String)
    timeframe = Column(String)
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    initial_capital = Column(Float)
    status = Column(String)  # pending, running, completed, failed
    results = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

class Strategy(Base):
    __tablename__ = "strategies"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    name = Column(String)
    description = Column(Text)
    code = Column(Text)
    parameters = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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

# 스레드 풀 설정
executor = ThreadPoolExecutor(max_workers=4)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class CustomStrategy(bt.Strategy):
    params = (
        ('fast_period', 10),
        ('slow_period', 20),
        ('rsi_period', 14),
        ('rsi_upper', 70),
        ('rsi_lower', 30),
    )

    def __init__(self):
        self.fast_ma = bt.indicators.SMA(period=self.p.fast_period)
        self.slow_ma = bt.indicators.SMA(period=self.p.slow_period)
        self.rsi = bt.indicators.RSI(period=self.p.rsi_period)
        self.crossover = bt.indicators.CrossOver(self.fast_ma, self.slow_ma)

    def next(self):
        if not self.position:
            if self.crossover > 0 and self.rsi < self.p.rsi_upper:
                self.buy()
        else:
            if self.crossover < 0 and self.rsi > self.p.rsi_lower:
                self.sell()

def run_backtest(backtest_id: int, db: SessionLocal):
    try:
        backtest = db.query(Backtest).filter(Backtest.id == backtest_id).first()
        if not backtest:
            logger.error(f"Backtest {backtest_id} not found")
            return

        backtest.status = 'running'
        db.commit()

        # 과거 데이터 가져오기
        response = requests.get(
            f"http://market-data-service:8080/historical/{backtest.symbol}",
            params={
                'start_date': backtest.start_date.isoformat(),
                'end_date': backtest.end_date.isoformat(),
                'timeframe': backtest.timeframe
            }
        )
        data = response.json()

        # 데이터프레임 생성
        df = pd.DataFrame(data)
        df['datetime'] = pd.to_datetime(df['timestamp'])
        df.set_index('datetime', inplace=True)

        # 백트레이더 설정
        cerebro = bt.Cerebro()
        cerebro.broker.setcash(backtest.initial_capital)
        cerebro.broker.setcommission(commission=0.001)  # 0.1% 수수료

        # 데이터 피드 생성
        data = bt.feeds.PandasData(
            dataname=df,
            datetime='datetime',
            open='open',
            high='high',
            low='low',
            close='close',
            volume='volume',
            openinterest=-1
        )
        cerebro.adddata(data)

        # 전략 추가
        cerebro.addstrategy(CustomStrategy)

        # 분석기 추가
        cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
        cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')

        # 백테스트 실행
        results = cerebro.run()
        strat = results[0]

        # 결과 수집
        sharpe = strat.analyzers.sharpe.get_analysis()
        drawdown = strat.analyzers.drawdown.get_analysis()
        returns = strat.analyzers.returns.get_analysis()
        trades = strat.analyzers.trades.get_analysis()

        # 결과 저장
        backtest.results = {
            'sharpe_ratio': sharpe['sharperatio'],
            'max_drawdown': drawdown['max']['drawdown'],
            'total_return': returns['rtot'],
            'annual_return': returns['rnorm100'],
            'total_trades': trades['total']['total'],
            'winning_trades': trades['won']['total'],
            'losing_trades': trades['lost']['total'],
            'win_rate': trades['won']['total'] / trades['total']['total'] if trades['total']['total'] > 0 else 0,
            'final_value': cerebro.broker.getvalue()
        }

        # 차트 생성
        plt.figure(figsize=(12, 8))
        cerebro.plot(style='candlestick', barup='green', bardown='red')
        plt.savefig('backtest_plot.png')
        plt.close()

        with open('backtest_plot.png', 'rb') as f:
            plot_data = base64.b64encode(f.read()).decode('utf-8')
            backtest.results['plot'] = plot_data

        backtest.status = 'completed'
        backtest.completed_at = datetime.utcnow()
        db.commit()

        # 결과 발행
        publish_backtest_results(backtest)

    except Exception as e:
        logger.error(f"Error running backtest: {str(e)}")
        backtest.status = 'failed'
        db.commit()

def publish_backtest_results(backtest: Backtest):
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=RABBITMQ_HOST, port=RABBITMQ_PORT)
        )
        channel = connection.channel()
        channel.exchange_declare(exchange='backtest_results', exchange_type='fanout')
        
        message = {
            'backtest_id': backtest.id,
            'user_id': backtest.user_id,
            'status': backtest.status,
            'results': backtest.results,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        channel.basic_publish(
            exchange='backtest_results',
            routing_key='',
            body=json.dumps(message)
        )
        connection.close()
    except Exception as e:
        logger.error(f"Error publishing backtest results: {str(e)}")

@app.on_event("startup")
async def startup_event():
    # Consul에 서비스 등록
    consul_client.agent.service.register(
        name='backtesting-service',
        service_id='backtesting-service-1',
        address='backtesting-service',
        port=8086,
        check=consul.Check.http(
            url='http://backtesting-service:8086/health',
            interval='10s',
            timeout='5s'
        )
    )
    # Prometheus 메트릭 서버 시작
    start_http_server(8000)

@app.get("/")
async def root():
    return {"message": "Backtesting Service"}

@app.post("/backtests")
async def create_backtest(
    user_id: int,
    strategy_name: str,
    symbol: str,
    timeframe: str,
    start_date: datetime,
    end_date: datetime,
    initial_capital: float,
    background_tasks: BackgroundTasks,
    db: SessionLocal = Depends(get_db)
):
    with tracer.start_span('create_backtest') as span:
        span.set_tag(tags.HTTP_METHOD, 'POST')
        span.set_tag(tags.HTTP_URL, '/backtests')
        
        backtest_requests.inc()
        start_time = time.time()
        
        try:
            backtest = Backtest(
                user_id=user_id,
                strategy_name=strategy_name,
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date,
                initial_capital=initial_capital,
                status='pending'
            )
            db.add(backtest)
            db.commit()
            db.refresh(backtest)
            
            # 백그라운드에서 백테스트 실행
            background_tasks.add_task(run_backtest, backtest.id, db)
            
            backtest_latency.observe(time.time() - start_time)
            return backtest
        except Exception as e:
            logger.error(f"Error creating backtest: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to create backtest")

@app.get("/backtests/{user_id}")
async def get_backtests(
    user_id: int,
    status: Optional[str] = None,
    db: SessionLocal = Depends(get_db)
):
    with tracer.start_span('get_backtests') as span:
        span.set_tag(tags.HTTP_METHOD, 'GET')
        span.set_tag(tags.HTTP_URL, f'/backtests/{user_id}')
        
        try:
            query = db.query(Backtest).filter(Backtest.user_id == user_id)
            if status:
                query = query.filter(Backtest.status == status)
            backtests = query.order_by(Backtest.created_at.desc()).all()
            return backtests
        except Exception as e:
            logger.error(f"Error fetching backtests: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch backtests")

@app.get("/backtests/{backtest_id}/results")
async def get_backtest_results(backtest_id: int, db: SessionLocal = Depends(get_db)):
    with tracer.start_span('get_backtest_results') as span:
        span.set_tag(tags.HTTP_METHOD, 'GET')
        span.set_tag(tags.HTTP_URL, f'/backtests/{backtest_id}/results')
        
        try:
            backtest = db.query(Backtest).filter(Backtest.id == backtest_id).first()
            if not backtest:
                raise HTTPException(status_code=404, detail="Backtest not found")
            return backtest.results
        except Exception as e:
            logger.error(f"Error fetching backtest results: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch backtest results")

@app.post("/strategies")
async def create_strategy(
    user_id: int,
    name: str,
    description: str,
    code: str,
    parameters: Dict,
    db: SessionLocal = Depends(get_db)
):
    with tracer.start_span('create_strategy') as span:
        span.set_tag(tags.HTTP_METHOD, 'POST')
        span.set_tag(tags.HTTP_URL, '/strategies')
        
        try:
            strategy = Strategy(
                user_id=user_id,
                name=name,
                description=description,
                code=code,
                parameters=parameters
            )
            db.add(strategy)
            db.commit()
            db.refresh(strategy)
            return strategy
        except Exception as e:
            logger.error(f"Error creating strategy: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to create strategy")

@app.get("/strategies/{user_id}")
async def get_strategies(user_id: int, db: SessionLocal = Depends(get_db)):
    with tracer.start_span('get_strategies') as span:
        span.set_tag(tags.HTTP_METHOD, 'GET')
        span.set_tag(tags.HTTP_URL, f'/strategies/{user_id}')
        
        try:
            strategies = db.query(Strategy).filter(Strategy.user_id == user_id).all()
            return strategies
        except Exception as e:
            logger.error(f"Error fetching strategies: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch strategies")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8086) 
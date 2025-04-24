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
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
import base64
from concurrent.futures import ThreadPoolExecutor
import asyncio
from sklearn.linear_model import LinearRegression
from statsmodels.tsa.stattools import adfuller
import statsmodels.api as sm

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Prometheus 메트릭
analysis_requests = Counter('analysis_requests_total', 'Total analysis requests')
analysis_latency = Histogram('analysis_latency_seconds', 'Analysis execution latency')

# Jaeger 설정
config = jaeger_client.Config(
    config={
        'sampler': {
            'type': 'const',
            'param': 1,
        },
        'logging': True,
    },
    service_name='analysis-service'
)
tracer = config.initialize_tracer()

# 데이터베이스 설정
DATABASE_URL = "postgresql://trading:trading123@postgres:5432/trading_db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 모델 정의
class Analysis(Base):
    __tablename__ = "analyses"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    type = Column(String)  # performance, risk, correlation, etc.
    parameters = Column(JSON)
    results = Column(JSON)
    status = Column(String)  # pending, running, completed, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

class Report(Base):
    __tablename__ = "reports"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    type = Column(String)  # daily, weekly, monthly
    content = Column(JSON)
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

# 스레드 풀 설정
executor = ThreadPoolExecutor(max_workers=4)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def analyze_performance(user_id: int, parameters: Dict, db: SessionLocal) -> Dict:
    try:
        # 거래 내역 가져오기
        response = requests.get(f"http://trading-service:8081/trades/{user_id}")
        trades = response.json()
        
        if not trades:
            return {"error": "No trades found"}
        
        # 데이터프레임 생성
        df = pd.DataFrame(trades)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        
        # 성과 지표 계산
        total_return = (df['profit'].sum() / df['amount'].sum()) * 100
        win_rate = (df['profit'] > 0).mean() * 100
        avg_win = df[df['profit'] > 0]['profit'].mean()
        avg_loss = df[df['profit'] < 0]['profit'].mean()
        
        # 월별 수익률 계산
        monthly_returns = df.resample('M')['profit'].sum() / df.resample('M')['amount'].sum() * 100
        
        # 차트 생성
        fig = make_subplots(rows=2, cols=1, subplot_titles=('월별 수익률', '누적 수익률'))
        
        # 월별 수익률 차트
        fig.add_trace(
            go.Bar(x=monthly_returns.index, y=monthly_returns.values, name='월별 수익률'),
            row=1, col=1
        )
        
        # 누적 수익률 차트
        cumulative_returns = (1 + monthly_returns/100).cumprod() - 1
        fig.add_trace(
            go.Scatter(x=cumulative_returns.index, y=cumulative_returns.values, name='누적 수익률'),
            row=2, col=1
        )
        
        # 차트 저장
        plot_data = fig.to_json()
        
        return {
            'total_return': total_return,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'monthly_returns': monthly_returns.to_dict(),
            'plot': plot_data
        }
    except Exception as e:
        logger.error(f"Error analyzing performance: {str(e)}")
        raise

def analyze_risk(user_id: int, parameters: Dict, db: SessionLocal) -> Dict:
    try:
        # 포지션 정보 가져오기
        response = requests.get(f"http://position-service:8084/positions/{user_id}")
        positions = response.json()
        
        if not positions:
            return {"error": "No positions found"}
        
        # 데이터프레임 생성
        df = pd.DataFrame(positions)
        
        # 위험 지표 계산
        total_exposure = df['amount'].sum()
        exposure_by_symbol = df.groupby('symbol')['amount'].sum()
        exposure_by_type = df.groupby('type')['amount'].sum()
        
        # VaR 계산
        returns = df['profit'] / df['amount']
        var_95 = np.percentile(returns, 5)
        var_99 = np.percentile(returns, 1)
        
        # 차트 생성
        fig = make_subplots(rows=2, cols=1, subplot_titles=('심볼별 노출', '포지션 타입별 노출'))
        
        # 심볼별 노출 차트
        fig.add_trace(
            go.Bar(x=exposure_by_symbol.index, y=exposure_by_symbol.values, name='심볼별 노출'),
            row=1, col=1
        )
        
        # 포지션 타입별 노출 차트
        fig.add_trace(
            go.Bar(x=exposure_by_type.index, y=exposure_by_type.values, name='포지션 타입별 노출'),
            row=2, col=1
        )
        
        # 차트 저장
        plot_data = fig.to_json()
        
        return {
            'total_exposure': total_exposure,
            'exposure_by_symbol': exposure_by_symbol.to_dict(),
            'exposure_by_type': exposure_by_type.to_dict(),
            'var_95': var_95,
            'var_99': var_99,
            'plot': plot_data
        }
    except Exception as e:
        logger.error(f"Error analyzing risk: {str(e)}")
        raise

def analyze_correlation(user_id: int, parameters: Dict, db: SessionLocal) -> Dict:
    try:
        # 시장 데이터 가져오기
        symbols = parameters.get('symbols', ['BTC', 'ETH', 'XRP'])
        start_date = parameters.get('start_date', (datetime.utcnow() - timedelta(days=30)).isoformat())
        end_date = parameters.get('end_date', datetime.utcnow().isoformat())
        
        data = {}
        for symbol in symbols:
            response = requests.get(
                f"http://market-data-service:8080/historical/{symbol}",
                params={
                    'start_date': start_date,
                    'end_date': end_date,
                    'timeframe': '1d'
                }
            )
            data[symbol] = response.json()
        
        # 데이터프레임 생성
        dfs = []
        for symbol, symbol_data in data.items():
            df = pd.DataFrame(symbol_data)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
            df = df[['close']].rename(columns={'close': symbol})
            dfs.append(df)
        
        df = pd.concat(dfs, axis=1)
        
        # 상관관계 계산
        correlation_matrix = df.corr()
        
        # 차트 생성
        fig = go.Figure(data=go.Heatmap(
            z=correlation_matrix.values,
            x=correlation_matrix.columns,
            y=correlation_matrix.index,
            colorscale='RdBu',
            zmin=-1,
            zmax=1
        ))
        
        # 차트 저장
        plot_data = fig.to_json()
        
        return {
            'correlation_matrix': correlation_matrix.to_dict(),
            'plot': plot_data
        }
    except Exception as e:
        logger.error(f"Error analyzing correlation: {str(e)}")
        raise

def run_analysis(analysis_id: int, db: SessionLocal):
    try:
        analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if not analysis:
            logger.error(f"Analysis {analysis_id} not found")
            return

        analysis.status = 'running'
        db.commit()

        # 분석 유형에 따른 처리
        if analysis.type == 'performance':
            results = analyze_performance(analysis.user_id, analysis.parameters, db)
        elif analysis.type == 'risk':
            results = analyze_risk(analysis.user_id, analysis.parameters, db)
        elif analysis.type == 'correlation':
            results = analyze_correlation(analysis.user_id, analysis.parameters, db)
        else:
            raise ValueError(f"Unknown analysis type: {analysis.type}")

        # 결과 저장
        analysis.results = results
        analysis.status = 'completed'
        analysis.completed_at = datetime.utcnow()
        db.commit()

        # 결과 발행
        publish_analysis_results(analysis)

    except Exception as e:
        logger.error(f"Error running analysis: {str(e)}")
        analysis.status = 'failed'
        db.commit()

def publish_analysis_results(analysis: Analysis):
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=RABBITMQ_HOST, port=RABBITMQ_PORT)
        )
        channel = connection.channel()
        channel.exchange_declare(exchange='analysis_results', exchange_type='fanout')
        
        message = {
            'analysis_id': analysis.id,
            'user_id': analysis.user_id,
            'type': analysis.type,
            'status': analysis.status,
            'results': analysis.results,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        channel.basic_publish(
            exchange='analysis_results',
            routing_key='',
            body=json.dumps(message)
        )
        connection.close()
    except Exception as e:
        logger.error(f"Error publishing analysis results: {str(e)}")

@app.on_event("startup")
async def startup_event():
    # Consul에 서비스 등록
    consul_client.agent.service.register(
        name='analysis-service',
        service_id='analysis-service-1',
        address='analysis-service',
        port=8087,
        check=consul.Check.http(
            url='http://analysis-service:8087/health',
            interval='10s',
            timeout='5s'
        )
    )
    # Prometheus 메트릭 서버 시작
    start_http_server(8000)

@app.get("/")
async def root():
    return {"message": "Analysis Service"}

@app.post("/analyses")
async def create_analysis(
    user_id: int,
    analysis_type: str,
    parameters: Dict,
    background_tasks: BackgroundTasks,
    db: SessionLocal = Depends(get_db)
):
    with tracer.start_span('create_analysis') as span:
        span.set_tag(tags.HTTP_METHOD, 'POST')
        span.set_tag(tags.HTTP_URL, '/analyses')
        
        analysis_requests.inc()
        start_time = time.time()
        
        try:
            analysis = Analysis(
                user_id=user_id,
                type=analysis_type,
                parameters=parameters,
                status='pending'
            )
            db.add(analysis)
            db.commit()
            db.refresh(analysis)
            
            # 백그라운드에서 분석 실행
            background_tasks.add_task(run_analysis, analysis.id, db)
            
            analysis_latency.observe(time.time() - start_time)
            return analysis
        except Exception as e:
            logger.error(f"Error creating analysis: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to create analysis")

@app.get("/analyses/{user_id}")
async def get_analyses(
    user_id: int,
    analysis_type: Optional[str] = None,
    status: Optional[str] = None,
    db: SessionLocal = Depends(get_db)
):
    with tracer.start_span('get_analyses') as span:
        span.set_tag(tags.HTTP_METHOD, 'GET')
        span.set_tag(tags.HTTP_URL, f'/analyses/{user_id}')
        
        try:
            query = db.query(Analysis).filter(Analysis.user_id == user_id)
            if analysis_type:
                query = query.filter(Analysis.type == analysis_type)
            if status:
                query = query.filter(Analysis.status == status)
            analyses = query.order_by(Analysis.created_at.desc()).all()
            return analyses
        except Exception as e:
            logger.error(f"Error fetching analyses: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch analyses")

@app.get("/analyses/{analysis_id}/results")
async def get_analysis_results(analysis_id: int, db: SessionLocal = Depends(get_db)):
    with tracer.start_span('get_analysis_results') as span:
        span.set_tag(tags.HTTP_METHOD, 'GET')
        span.set_tag(tags.HTTP_URL, f'/analyses/{analysis_id}/results')
        
        try:
            analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
            if not analysis:
                raise HTTPException(status_code=404, detail="Analysis not found")
            return analysis.results
        except Exception as e:
            logger.error(f"Error fetching analysis results: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch analysis results")

@app.post("/reports")
async def create_report(
    user_id: int,
    report_type: str,
    content: Dict,
    db: SessionLocal = Depends(get_db)
):
    with tracer.start_span('create_report') as span:
        span.set_tag(tags.HTTP_METHOD, 'POST')
        span.set_tag(tags.HTTP_URL, '/reports')
        
        try:
            report = Report(
                user_id=user_id,
                type=report_type,
                content=content
            )
            db.add(report)
            db.commit()
            db.refresh(report)
            return report
        except Exception as e:
            logger.error(f"Error creating report: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to create report")

@app.get("/reports/{user_id}")
async def get_reports(
    user_id: int,
    report_type: Optional[str] = None,
    db: SessionLocal = Depends(get_db)
):
    with tracer.start_span('get_reports') as span:
        span.set_tag(tags.HTTP_METHOD, 'GET')
        span.set_tag(tags.HTTP_URL, f'/reports/{user_id}')
        
        try:
            query = db.query(Report).filter(Report.user_id == user_id)
            if report_type:
                query = query.filter(Report.type == report_type)
            reports = query.order_by(Report.created_at.desc()).all()
            return reports
        except Exception as e:
            logger.error(f"Error fetching reports: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch reports")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8087) 
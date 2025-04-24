from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
from dotenv import load_dotenv
import requests
import json
import time
import websockets
import asyncio
from typing import List, Dict
import logging
from prometheus_client import Counter, Histogram, start_http_server
import consul
import jaeger_client
from opentracing.ext import tags
from opentracing.propagation import Format

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Prometheus 메트릭
market_data_requests = Counter('market_data_requests_total', 'Total market data requests')
market_data_latency = Histogram('market_data_latency_seconds', 'Market data request latency')

# Jaeger 설정
config = jaeger_client.Config(
    config={
        'sampler': {
            'type': 'const',
            'param': 1,
        },
        'logging': True,
    },
    service_name='market-data-service'
)
tracer = config.initialize_tracer()

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
UPBIT_WS_URL = "wss://api.upbit.com/websocket/v1"
SUPPORTED_COINS = ["BTC", "ETH", "XRP", "SOL", "ADA"]

# Consul 클라이언트 설정
consul_client = consul.Consul(host='consul', port=8500)

@app.on_event("startup")
async def startup_event():
    # Consul에 서비스 등록
    consul_client.agent.service.register(
        name='market-data-service',
        service_id='market-data-service-1',
        address='market-data-service',
        port=8080,
        check=consul.Check.http(
            url='http://market-data-service:8080/health',
            interval='10s',
            timeout='5s'
        )
    )
    # Prometheus 메트릭 서버 시작
    start_http_server(8000)

@app.get("/")
async def root():
    return {"message": "Market Data Service"}

@app.get("/market-data")
async def get_market_data():
    with tracer.start_span('get_market_data') as span:
        span.set_tag(tags.HTTP_METHOD, 'GET')
        span.set_tag(tags.HTTP_URL, '/market-data')
        
        market_data_requests.inc()
        start_time = time.time()
        
        try:
            response = requests.get(f"{UPBIT_API_URL}/ticker?markets=KRW-{','.join(SUPPORTED_COINS)}")
            data = response.json()
            
            market_data_latency.observe(time.time() - start_time)
            return data
        except Exception as e:
            logger.error(f"Error fetching market data: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch market data")

@app.get("/top-coins")
async def get_top_coins():
    with tracer.start_span('get_top_coins') as span:
        span.set_tag(tags.HTTP_METHOD, 'GET')
        span.set_tag(tags.HTTP_URL, '/top-coins')
        
        try:
            response = requests.get(f"{UPBIT_API_URL}/ticker?markets=KRW-{','.join(SUPPORTED_COINS)}")
            data = response.json()
            
            # 24시간 거래량 기준 정렬
            sorted_coins = sorted(data, key=lambda x: float(x['acc_trade_price_24h']), reverse=True)
            return sorted_coins[:3]
        except Exception as e:
            logger.error(f"Error fetching top coins: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch top coins")

@app.get("/coin/{symbol}")
async def get_coin_data(symbol: str):
    with tracer.start_span('get_coin_data') as span:
        span.set_tag(tags.HTTP_METHOD, 'GET')
        span.set_tag(tags.HTTP_URL, f'/coin/{symbol}')
        span.set_tag('coin.symbol', symbol)
        
        if symbol.upper() not in SUPPORTED_COINS:
            raise HTTPException(status_code=400, detail="Unsupported coin")
        
        try:
            response = requests.get(f"{UPBIT_API_URL}/ticker?markets=KRW-{symbol.upper()}")
            data = response.json()
            return data[0] if data else None
        except Exception as e:
            logger.error(f"Error fetching coin data: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch coin data")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

async def websocket_client():
    while True:
        try:
            async with websockets.connect(UPBIT_WS_URL) as websocket:
                # 구독 메시지 생성
                subscribe_message = [
                    {"ticket": "market-data-service"},
                    {"type": "ticker", "codes": [f"KRW-{coin}" for coin in SUPPORTED_COINS]}
                ]
                await websocket.send(json.dumps(subscribe_message))
                
                while True:
                    message = await websocket.recv()
                    # 여기서 메시지 처리 및 저장 로직 구현
                    logger.info(f"Received market data: {message}")
        except Exception as e:
            logger.error(f"WebSocket error: {str(e)}")
            await asyncio.sleep(5)  # 재연결 전 대기

if __name__ == "__main__":
    # WebSocket 클라이언트 시작
    asyncio.create_task(websocket_client())
    uvicorn.run(app, host="0.0.0.0", port=8080) 
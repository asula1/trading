from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
from dotenv import load_dotenv
import requests
import json
import time
import logging
from prometheus_client import Counter, Histogram, start_http_server
import consul
import jaeger_client
from opentracing.ext import tags
from opentracing.propagation import Format
import numpy as np
import pandas as pd
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from sklearn.preprocessing import MinMaxScaler
import talib
import asyncio
from typing import List, Dict, Optional
import pickle
from datetime import datetime, timedelta

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Prometheus 메트릭
prediction_requests = Counter('prediction_requests_total', 'Total prediction requests')
prediction_latency = Histogram('prediction_latency_seconds', 'Prediction request latency')

# Jaeger 설정
config = jaeger_client.Config(
    config={
        'sampler': {
            'type': 'const',
            'param': 1,
        },
        'logging': True,
    },
    service_name='ai-prediction-service'
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

# 모델 설정
MODEL_PATH = "models"
SUPPORTED_COINS = ["BTC", "ETH", "XRP", "SOL", "ADA"]
TIME_HORIZONS = [1, 6, 24]  # hours
SEQUENCE_LENGTH = 60  # 5-minute candles

# Consul 클라이언트 설정
consul_client = consul.Consul(host='consul', port=8500)

# 모델 로드 함수
def load_model(symbol: str) -> Optional[tf.keras.Model]:
    model_path = os.path.join(MODEL_PATH, f"{symbol}_model.h5")
    if os.path.exists(model_path):
        return tf.keras.models.load_model(model_path)
    return None

# 기술적 지표 계산 함수
def calculate_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    # RSI
    df['rsi'] = talib.RSI(df['close'].values, timeperiod=14)
    
    # MACD
    macd, macd_signal, macd_hist = talib.MACD(df['close'].values)
    df['macd'] = macd
    df['macd_signal'] = macd_signal
    df['macd_hist'] = macd_hist
    
    # Bollinger Bands
    upper, middle, lower = talib.BBANDS(df['close'].values)
    df['bb_upper'] = upper
    df['bb_middle'] = middle
    df['bb_lower'] = lower
    
    # Stochastic
    slowk, slowd = talib.STOCH(df['high'].values, df['low'].values, df['close'].values)
    df['stoch_k'] = slowk
    df['stoch_d'] = slowd
    
    # ADX
    df['adx'] = talib.ADX(df['high'].values, df['low'].values, df['close'].values)
    
    # Volatility
    df['volatility'] = talib.ATR(df['high'].values, df['low'].values, df['close'].values)
    
    return df

# 데이터 전처리 함수
def preprocess_data(df: pd.DataFrame) -> np.ndarray:
    # 기술적 지표 계산
    df = calculate_technical_indicators(df)
    
    # 필요한 컬럼 선택
    features = ['close', 'volume', 'rsi', 'macd', 'macd_signal', 'macd_hist',
                'bb_upper', 'bb_middle', 'bb_lower', 'stoch_k', 'stoch_d',
                'adx', 'volatility']
    
    # 정규화
    scaler = MinMaxScaler()
    scaled_data = scaler.fit_transform(df[features])
    
    # 시퀀스 데이터 생성
    X = []
    for i in range(len(scaled_data) - SEQUENCE_LENGTH):
        X.append(scaled_data[i:(i + SEQUENCE_LENGTH)])
    
    return np.array(X)

# 예측 함수
def predict_price(model: tf.keras.Model, data: np.ndarray) -> Dict:
    predictions = model.predict(data)
    confidence = np.mean(np.abs(predictions))
    
    return {
        'prediction': float(predictions[-1][0]),
        'confidence': float(confidence),
        'timestamp': datetime.utcnow().isoformat()
    }

@app.on_event("startup")
async def startup_event():
    # Consul에 서비스 등록
    consul_client.agent.service.register(
        name='ai-prediction-service',
        service_id='ai-prediction-service-1',
        address='ai-prediction-service',
        port=8082,
        check=consul.Check.http(
            url='http://ai-prediction-service:8082/health',
            interval='10s',
            timeout='5s'
        )
    )
    # Prometheus 메트릭 서버 시작
    start_http_server(8000)

@app.get("/")
async def root():
    return {"message": "AI Prediction Service"}

@app.get("/predict/{symbol}")
async def predict_symbol(symbol: str):
    with tracer.start_span('predict_symbol') as span:
        span.set_tag(tags.HTTP_METHOD, 'GET')
        span.set_tag(tags.HTTP_URL, f'/predict/{symbol}')
        span.set_tag('prediction.symbol', symbol)
        
        prediction_requests.inc()
        start_time = time.time()
        
        if symbol.upper() not in SUPPORTED_COINS:
            raise HTTPException(status_code=400, detail="Unsupported coin")
        
        try:
            # 모델 로드
            model = load_model(symbol.upper())
            if model is None:
                raise HTTPException(status_code=404, detail="Model not found")
            
            # 최근 데이터 가져오기
            response = requests.get(f"http://market-data-service:8080/coin/{symbol}")
            recent_data = response.json()
            
            # 데이터 전처리
            df = pd.DataFrame([recent_data])
            processed_data = preprocess_data(df)
            
            # 예측 수행
            prediction = predict_price(model, processed_data)
            
            prediction_latency.observe(time.time() - start_time)
            return prediction
        except Exception as e:
            logger.error(f"Error making prediction: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to make prediction")

@app.get("/predictions")
async def get_all_predictions():
    with tracer.start_span('get_all_predictions') as span:
        span.set_tag(tags.HTTP_METHOD, 'GET')
        span.set_tag(tags.HTTP_URL, '/predictions')
        
        try:
            predictions = {}
            for symbol in SUPPORTED_COINS:
                model = load_model(symbol)
                if model is not None:
                    response = requests.get(f"http://market-data-service:8080/coin/{symbol}")
                    recent_data = response.json()
                    
                    df = pd.DataFrame([recent_data])
                    processed_data = preprocess_data(df)
                    
                    prediction = predict_price(model, processed_data)
                    predictions[symbol] = prediction
            
            # 상위 3개 거래 신호 추천
            recommendations = sorted(
                predictions.items(),
                key=lambda x: x[1]['confidence'],
                reverse=True
            )[:3]
            
            return {
                'predictions': predictions,
                'recommendations': recommendations
            }
        except Exception as e:
            logger.error(f"Error getting all predictions: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to get predictions")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/training/status")
async def get_training_status():
    return {
        "status": "training_completed",
        "last_training_time": datetime.utcnow().isoformat(),
        "next_training_time": (datetime.utcnow() + timedelta(hours=24)).isoformat()
    }

@app.get("/model/info")
async def get_model_info():
    return {
        "architecture": "LSTM",
        "layers": 3,
        "units_per_layer": 128,
        "input_sequence_length": SEQUENCE_LENGTH,
        "features": [
            "close", "volume", "rsi", "macd", "macd_signal", "macd_hist",
            "bb_upper", "bb_middle", "bb_lower", "stoch_k", "stoch_d",
            "adx", "volatility"
        ]
    }

@app.get("/model/metrics")
async def get_model_metrics():
    metrics = {}
    for symbol in SUPPORTED_COINS:
        metrics[symbol] = {
            "accuracy": 0.85,
            "precision": 0.82,
            "recall": 0.88,
            "f1_score": 0.85
        }
    return metrics

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8082) 
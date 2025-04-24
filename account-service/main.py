from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
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
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Prometheus 메트릭
auth_requests = Counter('auth_requests_total', 'Total authentication requests')
auth_latency = Histogram('auth_latency_seconds', 'Authentication request latency')

# Jaeger 설정
config = jaeger_client.Config(
    config={
        'sampler': {
            'type': 'const',
            'param': 1,
        },
        'logging': True,
    },
    service_name='account-service'
)
tracer = config.initialize_tracer()

# 데이터베이스 설정
DATABASE_URL = "postgresql://trading:trading123@postgres:5432/trading_db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 모델 정의
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)

class APIKey(Base):
    __tablename__ = "api_keys"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    exchange = Column(String)
    api_key = Column(String)
    api_secret = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

# JWT 설정
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

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

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), db: SessionLocal = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user

@app.on_event("startup")
async def startup_event():
    # Consul에 서비스 등록
    consul_client.agent.service.register(
        name='account-service',
        service_id='account-service-1',
        address='account-service',
        port=8083,
        check=consul.Check.http(
            url='http://account-service:8083/health',
            interval='10s',
            timeout='5s'
        )
    )
    # Prometheus 메트릭 서버 시작
    start_http_server(8000)

@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: SessionLocal = Depends(get_db)):
    with tracer.start_span('login') as span:
        span.set_tag(tags.HTTP_METHOD, 'POST')
        span.set_tag(tags.HTTP_URL, '/token')
        
        auth_requests.inc()
        start_time = time.time()
        
        user = db.query(User).filter(User.username == form_data.username).first()
        if not user or not verify_password(form_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username}, expires_delta=access_token_expires
        )
        
        user.last_login = datetime.utcnow()
        db.commit()
        
        auth_latency.observe(time.time() - start_time)
        return {"access_token": access_token, "token_type": "bearer"}

@app.post("/register")
async def register(username: str, email: str, password: str, db: SessionLocal = Depends(get_db)):
    with tracer.start_span('register') as span:
        span.set_tag(tags.HTTP_METHOD, 'POST')
        span.set_tag(tags.HTTP_URL, '/register')
        
        # 사용자 이름 중복 확인
        if db.query(User).filter(User.username == username).first():
            raise HTTPException(status_code=400, detail="Username already registered")
        
        # 이메일 중복 확인
        if db.query(User).filter(User.email == email).first():
            raise HTTPException(status_code=400, detail="Email already registered")
        
        # 새 사용자 생성
        hashed_password = get_password_hash(password)
        user = User(
            username=username,
            email=email,
            hashed_password=hashed_password
        )
        db.add(user)
        db.commit()
        
        return {"message": "User registered successfully"}

@app.post("/api-keys")
async def add_api_key(
    exchange: str,
    api_key: str,
    api_secret: str,
    current_user: User = Depends(get_current_user),
    db: SessionLocal = Depends(get_db)
):
    with tracer.start_span('add_api_key') as span:
        span.set_tag(tags.HTTP_METHOD, 'POST')
        span.set_tag(tags.HTTP_URL, '/api-keys')
        
        # API 키 저장
        new_api_key = APIKey(
            user_id=current_user.id,
            exchange=exchange,
            api_key=api_key,
            api_secret=api_secret
        )
        db.add(new_api_key)
        db.commit()
        
        return {"message": "API key added successfully"}

@app.get("/api-keys")
async def get_api_keys(
    current_user: User = Depends(get_current_user),
    db: SessionLocal = Depends(get_db)
):
    with tracer.start_span('get_api_keys') as span:
        span.set_tag(tags.HTTP_METHOD, 'GET')
        span.set_tag(tags.HTTP_URL, '/api-keys')
        
        api_keys = db.query(APIKey).filter(
            APIKey.user_id == current_user.id,
            APIKey.is_active == True
        ).all()
        
        return api_keys

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8083) 
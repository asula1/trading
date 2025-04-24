import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from contextlib import contextmanager

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 환경 변수 로드
load_dotenv()

# 데이터베이스 연결 설정
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "monitoring")

# 데이터베이스 URL 구성
DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

# 데이터베이스 엔진 생성
try:
    engine = create_engine(
        DATABASE_URL,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=1800,
        echo=False
    )
    logger.info("데이터베이스 엔진 생성 완료")
except Exception as e:
    logger.error(f"데이터베이스 엔진 생성 실패: {e}")
    raise

# 세션 팩토리 생성
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 베이스 모델
Base = declarative_base()

@contextmanager
def get_db():
    """데이터베이스 세션 컨텍스트 매니저"""
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"데이터베이스 오류 발생: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()

def init_db():
    """데이터베이스 초기화"""
    try:
        # 테이블 생성
        Base.metadata.create_all(bind=engine)
        logger.info("데이터베이스 테이블이 생성되었습니다.")
        
        # 기본 알림 설정 생성
        from .models import AlertConfig
        db = SessionLocal()
        try:
            # 시스템 알림 설정
            system_alerts = [
                {
                    "alert_type": "high_cpu_usage",
                    "severity": "warning",
                    "threshold": 80.0,
                    "email_recipients": "[]",
                    "enabled": True
                },
                {
                    "alert_type": "critical_cpu_usage",
                    "severity": "critical",
                    "threshold": 90.0,
                    "email_recipients": "[]",
                    "enabled": True
                },
                {
                    "alert_type": "high_memory_usage",
                    "severity": "warning",
                    "threshold": 85.0,
                    "email_recipients": "[]",
                    "enabled": True
                },
                {
                    "alert_type": "critical_memory_usage",
                    "severity": "critical",
                    "threshold": 95.0,
                    "email_recipients": "[]",
                    "enabled": True
                },
                {
                    "alert_type": "high_disk_usage",
                    "severity": "warning",
                    "threshold": 85.0,
                    "email_recipients": "[]",
                    "enabled": True
                },
                {
                    "alert_type": "critical_disk_usage",
                    "severity": "critical",
                    "threshold": 95.0,
                    "email_recipients": "[]",
                    "enabled": True
                }
            ]
            
            # 서비스 알림 설정
            service_alerts = [
                {
                    "alert_type": "service_down",
                    "severity": "critical",
                    "threshold": None,
                    "email_recipients": "[]",
                    "enabled": True
                },
                {
                    "alert_type": "high_latency",
                    "severity": "warning",
                    "threshold": 1.0,  # 1초
                    "email_recipients": "[]",
                    "enabled": True
                }
            ]
            
            # 컨테이너 알림 설정
            container_alerts = [
                {
                    "alert_type": "container_high_memory",
                    "severity": "warning",
                    "threshold": 80.0,
                    "email_recipients": "[]",
                    "enabled": True
                },
                {
                    "alert_type": "container_high_cpu",
                    "severity": "warning",
                    "threshold": 80.0,
                    "email_recipients": "[]",
                    "enabled": True
                }
            ]
            
            # 모든 알림 설정 생성
            for alert_config in system_alerts + service_alerts + container_alerts:
                config = AlertConfig(**alert_config)
                db.add(config)
            
            db.commit()
            logger.info("기본 알림 설정이 생성되었습니다.")
            
        except Exception as e:
            logger.error(f"기본 알림 설정 생성 중 오류 발생: {str(e)}")
            db.rollback()
            raise
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"데이터베이스 초기화 중 오류 발생: {str(e)}")
        raise

def check_db_connection():
    """데이터베이스 연결 확인"""
    try:
        with engine.connect() as connection:
            connection.execute("SELECT 1")
        logger.info("데이터베이스 연결 확인 완료")
        return True
    except Exception as e:
        logger.error(f"데이터베이스 연결 확인 실패: {e}")
        return False 
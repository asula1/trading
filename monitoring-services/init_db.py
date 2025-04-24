import os
import logging
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_database():
    try:
        # 데이터베이스 연결 정보
        db_params = {
            'host': os.getenv('DB_HOST', 'postgres'),
            'user': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASSWORD', 'postgres'),
            'port': os.getenv('DB_PORT', '5432')
        }
        
        # 데이터베이스 생성
        conn = psycopg2.connect(**db_params)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        
        # 데이터베이스가 없으면 생성
        db_name = os.getenv('DB_NAME', 'tradingdb')
        cur.execute(f"SELECT 1 FROM pg_database WHERE datname = '{db_name}'")
        if not cur.fetchone():
            cur.execute(f'CREATE DATABASE {db_name}')
            logger.info(f"Database {db_name} created successfully")
        
        cur.close()
        conn.close()
        
        # 스키마 생성
        conn = psycopg2.connect(**db_params, database=db_name)
        cur = conn.cursor()
        
        # 스키마 파일 읽기
        with open('schema.sql', 'r') as f:
            schema_sql = f.read()
        
        # 스키마 실행
        cur.execute(schema_sql)
        conn.commit()
        logger.info("Database schema created successfully")
        
        # 초기 서비스 상태 데이터 삽입
        services = [
            'market-data-service',
            'trading-service',
            'ai-prediction-service',
            'account-service',
            'position-service',
            'risk-management-service',
            'backtesting-service',
            'analysis-services',
            'monitoring-service'
        ]
        
        for service in services:
            cur.execute("""
                INSERT INTO service_status (service_name, status, last_check)
                VALUES (%s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (service_name) DO NOTHING
            """, (service, 'unknown'))
        
        conn.commit()
        logger.info("Initial service status data inserted")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        raise

if __name__ == "__main__":
    init_database() 
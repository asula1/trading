import os
import sys
import logging
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_db_connection():
    """데이터베이스 연결을 생성합니다."""
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=os.getenv('DB_PORT', '5432'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', 'postgres'),
            dbname='postgres'  # 초기 연결은 postgres 데이터베이스로
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        return conn
    except Exception as e:
        logger.error(f"데이터베이스 연결 실패: {e}")
        sys.exit(1)

def create_database(conn):
    """데이터베이스를 생성합니다."""
    db_name = os.getenv('DB_NAME', 'monitoring')
    try:
        with conn.cursor() as cur:
            # 데이터베이스가 존재하는지 확인
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
            if not cur.fetchone():
                cur.execute(f"CREATE DATABASE {db_name}")
                logger.info(f"데이터베이스 {db_name} 생성 완료")
            else:
                logger.info(f"데이터베이스 {db_name}가 이미 존재합니다")
    except Exception as e:
        logger.error(f"데이터베이스 생성 실패: {e}")
        sys.exit(1)

def create_tables(conn):
    """필요한 테이블들을 생성합니다."""
    db_name = os.getenv('DB_NAME', 'monitoring')
    try:
        # 모니터링 데이터베이스에 연결
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=os.getenv('DB_PORT', '5432'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', 'postgres'),
            dbname=db_name
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)

        with conn.cursor() as cur:
            # 시스템 메트릭 테이블
            cur.execute("""
                CREATE TABLE IF NOT EXISTS system_metrics (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP NOT NULL,
                    cpu_usage FLOAT NOT NULL,
                    memory_usage FLOAT NOT NULL,
                    disk_usage FLOAT NOT NULL,
                    network_in_bytes BIGINT NOT NULL,
                    network_out_bytes BIGINT NOT NULL
                )
            """)

            # 서비스 상태 테이블
            cur.execute("""
                CREATE TABLE IF NOT EXISTS service_status (
                    id SERIAL PRIMARY KEY,
                    service_name VARCHAR(255) NOT NULL,
                    status VARCHAR(50) NOT NULL,
                    last_check TIMESTAMP NOT NULL,
                    tags TEXT[],
                    UNIQUE(service_name)
                )
            """)

            # 알림 설정 테이블
            cur.execute("""
                CREATE TABLE IF NOT EXISTS alert_config (
                    id SERIAL PRIMARY KEY,
                    alert_type VARCHAR(50) NOT NULL,
                    threshold FLOAT NOT NULL,
                    cooldown_seconds INTEGER NOT NULL,
                    notification_channels TEXT[] NOT NULL,
                    UNIQUE(alert_type)
                )
            """)

            # 알림 기록 테이블
            cur.execute("""
                CREATE TABLE IF NOT EXISTS alert_history (
                    id SERIAL PRIMARY KEY,
                    alert_type VARCHAR(50) NOT NULL,
                    message TEXT NOT NULL,
                    severity VARCHAR(20) NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    resolved BOOLEAN DEFAULT FALSE,
                    resolved_at TIMESTAMP
                )
            """)

            # 기본 알림 설정 삽입
            cur.execute("""
                INSERT INTO alert_config (alert_type, threshold, cooldown_seconds, notification_channels)
                VALUES 
                    ('cpu', 80.0, 300, ARRAY['email', 'slack']),
                    ('memory', 80.0, 300, ARRAY['email', 'slack']),
                    ('disk', 90.0, 300, ARRAY['email', 'slack']),
                    ('network', 1000000.0, 300, ARRAY['email', 'slack'])
                ON CONFLICT (alert_type) DO NOTHING
            """)

            logger.info("테이블 생성 및 기본 설정 완료")

    except Exception as e:
        logger.error(f"테이블 생성 실패: {e}")
        sys.exit(1)
    finally:
        conn.close()

def main():
    """메인 함수"""
    # 환경 변수 로드
    load_dotenv()

    # 데이터베이스 연결
    conn = get_db_connection()
    
    try:
        # 데이터베이스 생성
        create_database(conn)
        
        # 테이블 생성
        create_tables(conn)
        
        logger.info("데이터베이스 설정이 완료되었습니다.")
    except Exception as e:
        logger.error(f"데이터베이스 설정 중 오류 발생: {e}")
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    main() 
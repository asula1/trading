-- 알림 테이블
CREATE TABLE IF NOT EXISTS alerts (
    id SERIAL PRIMARY KEY,
    service VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    message TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved BOOLEAN NOT NULL DEFAULT FALSE
);

-- 시스템 메트릭 테이블
CREATE TABLE IF NOT EXISTS system_metrics (
    id SERIAL PRIMARY KEY,
    cpu_usage FLOAT NOT NULL,
    memory_usage FLOAT NOT NULL,
    disk_usage FLOAT NOT NULL,
    network_incoming BIGINT NOT NULL,
    network_outgoing BIGINT NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 서비스 상태 테이블
CREATE TABLE IF NOT EXISTS service_status (
    id SERIAL PRIMARY KEY,
    service_name VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    last_check TIMESTAMP NOT NULL,
    details JSONB,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 거래 메트릭 테이블
CREATE TABLE IF NOT EXISTS trading_metrics (
    id SERIAL PRIMARY KEY,
    total_trades INTEGER NOT NULL,
    avg_trade_amount DECIMAL(20,8) NOT NULL,
    completed_trades INTEGER NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_alerts_service ON alerts(service);
CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts(timestamp);
CREATE INDEX IF NOT EXISTS idx_system_metrics_timestamp ON system_metrics(timestamp);
CREATE INDEX IF NOT EXISTS idx_service_status_service ON service_status(service_name);
CREATE INDEX IF NOT EXISTS idx_service_status_timestamp ON service_status(timestamp);
CREATE INDEX IF NOT EXISTS idx_trading_metrics_timestamp ON trading_metrics(timestamp); 
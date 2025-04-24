# 모니터링 서비스 API 문서

## 개요

이 문서는 모니터링 서비스의 API 엔드포인트와 사용 방법을 설명합니다. 모든 API는 JSON 형식으로 요청과 응답을 처리합니다.

## 기본 정보

- 기본 URL: `http://localhost:8000`
- 응답 형식: JSON
- 인증: 현재 인증이 필요하지 않음

## API 엔드포인트

### 1. 시스템 메트릭 API

#### 시스템 메트릭 생성
```http
POST /metrics/system
```

**요청 본문:**
```json
{
  "cpu_usage": 45.5,
  "memory_usage": 60.2,
  "disk_usage": 75.8,
  "network_in": 1024.5,
  "network_out": 512.3
}
```

**응답:**
```json
{
  "id": 1,
  "cpu_usage": 45.5,
  "memory_usage": 60.2,
  "disk_usage": 75.8,
  "network_in": 1024.5,
  "network_out": 512.3,
  "timestamp": "2024-01-01T00:00:00"
}
```

#### 시스템 메트릭 조회
```http
GET /metrics/system?start_time=2024-01-01T00:00:00&end_time=2024-01-02T00:00:00&limit=100
```

**쿼리 파라미터:**
- `start_time`: 시작 시간 (선택)
- `end_time`: 종료 시간 (선택)
- `limit`: 조회할 레코드 수 (기본값: 100)

### 2. 서비스 상태 API

#### 서비스 상태 생성
```http
POST /services/status
```

**요청 본문:**
```json
{
  "service_name": "api-service",
  "is_healthy": true,
  "response_time": 0.5,
  "error_message": null
}
```

#### 서비스 상태 조회
```http
GET /services/status?service_name=api-service&is_healthy=true&limit=100
```

**쿼리 파라미터:**
- `service_name`: 서비스 이름 (선택)
- `is_healthy`: 건강 상태 (선택)
- `limit`: 조회할 레코드 수 (기본값: 100)

### 3. 알림 설정 API

#### 알림 설정 생성
```http
POST /alerts/config
```

**요청 본문:**
```json
{
  "alert_type": "high_cpu_usage",
  "enabled": true,
  "email_enabled": true,
  "slack_enabled": true,
  "email_recipients": ["admin@example.com"],
  "severity": "warning",
  "threshold": 80.0,
  "cooldown_period": 300
}
```

#### 알림 설정 조회
```http
GET /alerts/config?alert_type=high_cpu_usage&enabled=true
```

#### 알림 설정 업데이트
```http
PUT /alerts/config/{config_id}
```

### 4. 알림 이력 API

#### 알림 이력 생성
```http
POST /alerts/history
```

**요청 본문:**
```json
{
  "alert_type": "high_cpu_usage",
  "severity": "warning",
  "message": "CPU 사용률이 80%를 초과했습니다",
  "resolved": false
}
```

#### 알림 이력 조회
```http
GET /alerts/history?alert_type=high_cpu_usage&severity=warning&resolved=false&start_time=2024-01-01T00:00:00&end_time=2024-01-02T00:00:00&limit=100
```

#### 알림 해결
```http
PUT /alerts/history/{history_id}/resolve?resolved_by=admin
```

### 5. 서비스 메트릭 API

#### 서비스 메트릭 생성
```http
POST /metrics/service
```

**요청 본문:**
```json
{
  "service_name": "api-service",
  "request_count": 1000,
  "error_count": 5,
  "avg_response_time": 0.5,
  "max_response_time": 1.2,
  "min_response_time": 0.1
}
```

#### 서비스 메트릭 조회
```http
GET /metrics/service?service_name=api-service&start_time=2024-01-01T00:00:00&end_time=2024-01-02T00:00:00&limit=100
```

### 6. 서비스 엔드포인트 API

#### 서비스 엔드포인트 생성
```http
POST /endpoints
```

**요청 본문:**
```json
{
  "service_name": "api-service",
  "endpoint_path": "/api/v1/users",
  "method": "GET",
  "is_monitored": true
}
```

#### 서비스 엔드포인트 조회
```http
GET /endpoints?service_name=api-service&is_monitored=true
```

### 7. 엔드포인트 메트릭 API

#### 엔드포인트 메트릭 생성
```http
POST /metrics/endpoint
```

**요청 본문:**
```json
{
  "endpoint_id": 1,
  "request_count": 100,
  "error_count": 2,
  "avg_response_time": 0.3,
  "max_response_time": 0.8,
  "min_response_time": 0.1
}
```

#### 엔드포인트 메트릭 조회
```http
GET /metrics/endpoint?endpoint_id=1&start_time=2024-01-01T00:00:00&end_time=2024-01-02T00:00:00&limit=100
```

## 에러 응답

모든 API는 다음과 같은 형식으로 에러를 반환합니다:

```json
{
  "error": "에러 메시지",
  "status_code": 400
}
```

## 성공 응답

성공적인 작업은 다음과 같은 형식으로 응답합니다:

```json
{
  "message": "성공 메시지",
  "status_code": 200
}
```

## 참고사항

1. 모든 시간은 ISO 8601 형식을 따릅니다.
2. 숫자 값은 소수점을 포함할 수 있습니다.
3. 필수 필드가 누락된 경우 400 Bad Request 에러가 반환됩니다.
4. 존재하지 않는 리소스에 접근할 경우 404 Not Found 에러가 반환됩니다.
5. 서버 내부 오류가 발생할 경우 500 Internal Server Error가 반환됩니다. 
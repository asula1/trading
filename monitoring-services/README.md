# 모니터링 서비스

시스템 및 서비스 모니터링을 위한 통합 모니터링 서비스입니다.

## 주요 기능

- 시스템 메트릭 수집 (CPU, 메모리, 디스크, 네트워크)
- 서비스 상태 모니터링
- 알림 설정 및 관리
- Prometheus 메트릭 노출
- Grafana 대시보드 연동

## 시스템 요구사항

- Python 3.9 이상
- Docker 및 Docker Compose
- PostgreSQL 13 이상
- Prometheus
- Grafana

## 설치 방법

1. 저장소 클론:
```bash
git clone https://github.com/your-username/monitoring-services.git
cd monitoring-services
```

2. 가상환경 생성 및 패키지 설치:
```bash
make install
```

3. 환경 변수 설정:
```bash
cp .env.example .env
# .env 파일을 편집하여 필요한 설정을 입력
```

4. 데이터베이스 초기화:
```bash
python -m app.database init
```

## 실행 방법

1. 개발 모드로 실행:
```bash
uvicorn app.main:app --reload
```

2. Docker Compose로 실행:
```bash
docker-compose up -d
```

## 테스트 실행

1. 기본 테스트:
```bash
make test
```

2. 커버리지 포함 테스트:
```bash
make test-cov
```

3. 린트 검사:
```bash
make lint
```

4. 코드 포맷팅:
```bash
make format
```

## API 문서

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 서비스 포트

- API 서버: 8000
- Prometheus: 9090
- Grafana: 3000
- PostgreSQL: 5432

## 기본 로그인 정보

- Grafana:
  - 사용자: admin
  - 비밀번호: admin

- PostgreSQL:
  - 사용자: postgres
  - 비밀번호: postgres
  - 데이터베이스: monitoring

## 모니터링 대시보드

1. 시스템 메트릭:
   - CPU 사용률
   - 메모리 사용량
   - 디스크 사용량
   - 네트워크 트래픽

2. 서비스 상태:
   - 서비스 가용성
   - 응답 시간
   - 에러율

3. 알림 설정:
   - 임계값 설정
   - 알림 채널 구성
   - 알림 기록 조회

## 문제 해결

1. 로그 확인:
```bash
docker-compose logs -f
```

2. 데이터베이스 백업:
```bash
docker-compose exec postgres pg_dump -U postgres monitoring > backup.sql
```

3. 데이터베이스 복원:
```bash
docker-compose exec -T postgres psql -U postgres monitoring < backup.sql
```

## 라이센스

MIT License

## 기여하기

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 연락처

프로젝트 관리자 - your-email@example.com

프로젝트 링크: [https://github.com/your-username/monitoring-services](https://github.com/your-username/monitoring-services) 
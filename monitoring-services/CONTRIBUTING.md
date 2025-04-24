# 기여 가이드

모니터링 서비스 프로젝트에 기여해 주셔서 감사합니다! 이 문서는 프로젝트에 기여하는 방법을 안내합니다.

## 시작하기 전에

1. [Code of Conduct](CODE_OF_CONDUCT.md)를 읽고 준수해 주세요.
2. GitHub 계정이 필요합니다.
3. Git과 GitHub 사용법에 대한 기본적인 이해가 필요합니다.

## 개발 환경 설정

1. 저장소 포크:
   - GitHub에서 이 저장소를 포크합니다.
   - 로컬에 클론합니다:
     ```bash
     git clone https://github.com/your-username/monitoring-services.git
     cd monitoring-services
     ```

2. 개발 환경 설정:
   ```bash
   make install
   cp .env.example .env
   ```

3. 테스트 실행:
   ```bash
   make test
   make lint
   ```

## 기여 프로세스

1. 브랜치 생성:
   ```bash
   git checkout -b feature/your-feature-name
   # 또는
   git checkout -b fix/your-bug-fix
   ```

2. 코드 작성:
   - 기능 추가 또는 버그 수정
   - 테스트 코드 작성
   - 문서 업데이트

3. 코드 포맷팅:
   ```bash
   make format
   ```

4. 변경사항 커밋:
   ```bash
   git add .
   git commit -m "설명: 변경사항에 대한 간단한 설명"
   ```

5. 원격 저장소에 푸시:
   ```bash
   git push origin feature/your-feature-name
   ```

6. Pull Request 생성:
   - GitHub에서 Pull Request를 생성합니다.
   - 변경사항에 대한 상세한 설명을 작성합니다.
   - 관련 이슈를 연결합니다.

## 코드 스타일 가이드

1. Python 코드 스타일:
   - PEP 8 준수
   - Black 포맷터 사용
   - isort로 import 정렬
   - flake8으로 린트 검사

2. 문서화:
   - 모든 함수와 클래스에 docstring 작성
   - 복잡한 로직에 주석 추가
   - README.md 및 API 문서 업데이트

3. 테스트:
   - 모든 새로운 기능에 대한 테스트 작성
   - 커버리지 80% 이상 유지
   - 테스트는 명확하고 이해하기 쉽게 작성

## Pull Request 체크리스트

- [ ] 코드가 PEP 8 스타일 가이드를 준수합니다.
- [ ] 모든 테스트가 통과합니다.
- [ ] 새로운 기능에 대한 테스트가 포함되어 있습니다.
- [ ] 문서가 업데이트되었습니다.
- [ ] 변경사항에 대한 설명이 명확합니다.
- [ ] 관련 이슈가 연결되어 있습니다.

## 이슈 보고

1. 버그 리포트:
   - 문제를 재현하는 단계를 포함
   - 예상되는 동작과 실제 동작을 설명
   - 환경 정보 제공 (OS, Python 버전 등)

2. 기능 요청:
   - 요청하는 기능을 명확히 설명
   - 사용 사례와 이점을 설명
   - 가능한 구현 방법을 제안

## 코드 리뷰 프로세스

1. Pull Request 생성 후:
   - CI 테스트가 실행됩니다.
   - 코드 커버리지가 계산됩니다.
   - 린트 검사가 실행됩니다.

2. 리뷰어가 할당되면:
   - 코드 리뷰를 진행합니다.
   - 필요한 경우 변경을 요청합니다.
   - 승인 후 메인 브랜치에 병합합니다.

## 질문과 지원

- GitHub Issues를 통해 질문을 남겨주세요.
- 프로젝트 관리자에게 직접 연락할 수도 있습니다.

## 감사의 말

프로젝트에 기여해 주셔서 감사합니다! 모든 기여는 프로젝트의 발전에 도움이 됩니다. 
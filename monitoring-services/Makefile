.PHONY: install test test-cov lint clean

# 환경 변수 설정
export PYTHONPATH := $(shell pwd)

# 기본 설정
VENV := venv
PYTHON := $(VENV)/Scripts/python
PIP := $(VENV)/Scripts/pip

# 가상환경 생성 및 패키지 설치
install:
	python -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

# 테스트 실행
test:
	$(PYTHON) -m pytest tests/ -v

# 커버리지 포함 테스트 실행
test-cov:
	$(PYTHON) -m pytest tests/ -v --cov=app --cov-report=term-missing --cov-report=html:coverage_report

# 린트 검사
lint:
	$(PYTHON) -m flake8 app/ tests/
	$(PYTHON) -m black --check app/ tests/
	$(PYTHON) -m isort --check-only app/ tests/

# 코드 포맷팅
format:
	$(PYTHON) -m black app/ tests/
	$(PYTHON) -m isort app/ tests/

# 정리
clean:
	rm -rf $(VENV)
	rm -rf .pytest_cache
	rm -rf coverage_report
	rm -rf __pycache__
	rm -rf */__pycache__
	rm -rf */*/__pycache__
	rm -rf .coverage 
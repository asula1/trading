#!/bin/bash

# 환경 변수 설정
export PYTHONPATH=$PYTHONPATH:$(pwd)

# 가상 환경 활성화 (선택사항)
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# 테스트 실행
echo "Running tests..."
pytest test_main.py -v --cov=main --cov-report=term-missing

# 테스트 결과에 따른 종료 코드 설정
if [ $? -eq 0 ]; then
    echo "All tests passed successfully!"
    exit 0
else
    echo "Some tests failed!"
    exit 1
fi 
import pytest
import sys
import os
from datetime import datetime

def run_tests():
    """테스트 실행 함수"""
    print(f"\n{'='*50}")
    print(f"테스트 실행 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}\n")
    
    # 테스트 디렉토리 설정
    test_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 테스트 실행 옵션
    pytest_args = [
        test_dir,  # 테스트 디렉토리
        "-v",      # 상세 출력
        "--tb=short",  # 짧은 에러 트레이스백
        "--cov=app",   # app 모듈 커버리지
        "--cov-report=term-missing",  # 누락된 라인 표시
        "--cov-report=html:coverage_report"  # HTML 커버리지 리포트
    ]
    
    # 테스트 실행
    exit_code = pytest.main(pytest_args)
    
    print(f"\n{'='*50}")
    print(f"테스트 실행 완료: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"종료 코드: {exit_code}")
    print(f"{'='*50}\n")
    
    return exit_code

if __name__ == "__main__":
    sys.exit(run_tests()) 
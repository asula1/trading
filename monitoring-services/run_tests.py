import os
import sys
import pytest
import logging
from datetime import datetime
from pathlib import Path

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('test_results.log')
    ]
)

logger = logging.getLogger(__name__)

def run_tests():
    """모든 테스트를 실행하고 결과를 보고합니다."""
    logger.info("테스트 실행을 시작합니다...")
    
    # 테스트 디렉토리 설정
    test_dir = Path(__file__).parent / 'tests'
    
    # 테스트 실행 시작 시간
    start_time = datetime.now()
    
    try:
        # pytest 실행
        result = pytest.main([
            str(test_dir),
            '-v',  # 상세 출력
            '--tb=short',  # 짧은 트레이스백
            '--cov=./',  # 코드 커버리지 측정
            '--cov-report=term-missing',  # 누락된 라인 보고
            '--cov-report=html:coverage_report'  # HTML 보고서 생성
        ])
        
        # 실행 시간 계산
        end_time = datetime.now()
        duration = end_time - start_time
        
        # 결과 로깅
        if result == 0:
            logger.info(f"모든 테스트가 성공적으로 완료되었습니다. (소요 시간: {duration})")
        else:
            logger.error(f"테스트 실행 중 오류가 발생했습니다. (소요 시간: {duration})")
            
        return result
        
    except Exception as e:
        logger.error(f"테스트 실행 중 예외가 발생했습니다: {str(e)}")
        return 1

def generate_test_report():
    """테스트 실행 결과 보고서를 생성합니다."""
    logger.info("테스트 보고서를 생성합니다...")
    
    # 테스트 결과 파일 경로
    log_file = 'test_results.log'
    coverage_dir = 'coverage_report'
    
    if not os.path.exists(log_file):
        logger.error("테스트 결과 로그 파일을 찾을 수 없습니다.")
        return
    
    # 테스트 결과 요약
    with open(log_file, 'r') as f:
        log_content = f.read()
        
    # 성공/실패 카운트
    success_count = log_content.count('PASSED')
    failure_count = log_content.count('FAILED')
    error_count = log_content.count('ERROR')
    
    # 보고서 생성
    report = f"""
테스트 실행 결과 보고서
=======================
실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

테스트 결과:
- 성공: {success_count}
- 실패: {failure_count}
- 오류: {error_count}

자세한 결과는 다음 파일에서 확인할 수 있습니다:
- 테스트 로그: {log_file}
- 커버리지 보고서: {coverage_dir}/index.html
"""
    
    # 보고서 저장
    with open('test_report.txt', 'w') as f:
        f.write(report)
    
    logger.info("테스트 보고서가 생성되었습니다.")

if __name__ == '__main__':
    # 테스트 실행
    test_result = run_tests()
    
    # 보고서 생성
    generate_test_report()
    
    # 종료 코드 반환
    sys.exit(test_result) 
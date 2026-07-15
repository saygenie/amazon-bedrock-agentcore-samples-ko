#!/usr/bin/env python3
"""
사실성 검사 모듈

이 모듈은 GitHub 워크플로에서 사실성 점수 검사 로직을 분리하고,
사실성 결과를 검증하는 재사용 가능 함수를 제공합니다.
"""

import sys
import json
from typing import Dict, Any


def load_factuality_results(
    results_file: str = "factuality_results.json",
) -> Dict[str, Any]:
    """
    JSON 파일에서 사실성 결과를 로드합니다.

    인수:
        results_file: 사실성 결과 JSON 파일 경로

    반환:
        사실성 결과가 포함된 딕셔너리

    예외:
        FileNotFoundError: 결과 파일이 없는 경우
        json.JSONDecodeError: 파일에 유효하지 않은 JSON이 포함된 경우
    """
    try:
        with open(results_file, "r") as f:
            results = json.load(f)
        return results
    except FileNotFoundError:
        print(f"✗ ERROR: {results_file} not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"✗ ERROR: Invalid JSON in {results_file}: {e}")
        sys.exit(1)


def print_factuality_summary(results: Dict[str, Any]) -> None:
    """
    사실성 결과 요약을 형식에 맞춰 출력합니다.

    인수:
        results: 사실성 결과가 포함된 딕셔너리
    """
    # 지표 추출
    avg_factuality = results["average_factuality_score"]
    total_items = results["total_items"]
    experiment_name = results["experiment_name"]

    print(f"Experiment: {experiment_name}")
    print(f"Total items evaluated: {total_items}")
    print(f"Average Factuality Score: {avg_factuality:.3f} ({avg_factuality * 100:.1f}%)")

    # 개별 점수 출력
    print("\nIndividual scores:")
    for i, score_data in enumerate(results["scores"]):
        print(f"  Item {i + 1}: {score_data['value']:.3f} ({score_data.get('name', 'Unknown')})")
        if score_data.get("comment"):
            print(f"    Comment: {score_data['comment']}")


def check_factuality_threshold(results: Dict[str, Any], threshold: float = 0.5) -> bool:
    """
    평균 사실성 점수가 임곗값 요구 사항을 충족하는지 확인합니다.

    인수:
        results: 사실성 결과가 포함된 딕셔너리
        threshold: 허용 가능한 최소 사실성 점수(기본값: 0.5)

    반환:
        점수가 임곗값을 충족하면 True, 그렇지 않으면 False
    """
    avg_factuality = results["average_factuality_score"]

    print(f"\nThreshold: {threshold * 100:.0f}%")

    if avg_factuality >= threshold:
        print(f"✓ PASSED: Factuality score {avg_factuality * 100:.1f}% is above {threshold * 100:.0f}%")
        return True
    else:
        print(f"✗ FAILED: Factuality score {avg_factuality * 100:.1f}% is below {threshold * 100:.0f}%")
        return False


def main(results_file: str = "factuality_results.json", threshold: float = 0.5) -> int:
    """
    사실성 결과를 검사하는 기본 함수입니다.

    인수:
        results_file: 사실성 결과 JSON 파일 경로
        threshold: 허용 가능한 최소 사실성 점수

    반환:
        종료 코드: 성공 시 0, 실패 시 1
    """
    # 파일에서 결과 로드
    results = load_factuality_results(results_file)

    # 요약 출력
    print_factuality_summary(results)

    # 임곗값 확인
    passed = check_factuality_threshold(results, threshold)

    return 0 if passed else 1


if __name__ == "__main__":
    # 명령줄 인수 파싱
    import argparse

    parser = argparse.ArgumentParser(description="Check factuality results from evaluation")
    parser.add_argument(
        "--results-file",
        "-f",
        default="factuality_results.json",
        help="Path to factuality results JSON file (default: factuality_results.json)",
    )
    parser.add_argument(
        "--threshold",
        "-t",
        type=float,
        default=0.5,
        help="Minimum acceptable factuality score (default: 0.5)",
    )

    args = parser.parse_args()

    # 검사 실행
    exit_code = main(args.results_file, args.threshold)
    sys.exit(exit_code)

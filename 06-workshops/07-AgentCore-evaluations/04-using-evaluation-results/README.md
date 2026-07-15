# 평가 분석기

**며칠 또는 몇 주가 걸리던 AI 에이전트 평가 분석을 몇 분 만에 처리하세요.**

<p align="center">
  <img src="assets/improvement_loop.svg" alt="AI 에이전트의 지속적 개선 순환 과정" width="700">
</p>

## 해결하려는 문제

AI 에이전트를 대규모로 평가하면 수백 개의 LLM-as-a-Judge 설명이 생성됩니다. 각 설명에는 해당 점수가 부여된 이유에 관한 상세한 추론이 포함됩니다. 사람이 이 모든 내용을 읽고 패턴을 찾기는 어렵습니다.

## 수행 작업

1. 평가 JSON 파일 **로드**
2. 점수가 낮은 평가 **필터링**(임계값 구성 가능)
3. AI를 사용하여 실패 패턴 **분석**
4. 구체적인 system prompt 수정안 **생성**

## 제공 결과

- LLM 판정자의 근거 인용문이 포함된 **상위 문제 3개**
- 정확한 prompt 변경 사항을 보여주는 **변경 전후 표**
- 바로 복사하여 사용할 수 있는 **수정된 전체 system prompt**

샘플 보고서는 [`example_agent_output.md`](example_agent_output.md)를 참조하세요.

## 빠른 시작

```bash
# 1. 종속성 설치
pip install -r requirements.txt

# 2. 데이터 추가
#    - 평가 JSON을 eval_data/에 배치
#    - 에이전트 prompt로 system_prompt.txt 편집

# 3. 노트북 실행
jupyter notebook evaluation_analyzer.ipynb
```

## 요구 사항

- Python 3.9+
- Amazon Bedrock용으로 구성된 AWS 자격 증명
- [Strands Evals](https://github.com/strands-agents/strands-evals) 또는 [AWS AgentCore](https://docs.aws.amazon.com/agentcore/)의 평가 데이터

---

전체 단계별 안내와 문서는 **[노트북 열기](evaluation_analyzer.ipynb)**에서 확인하세요.

# AgentCore CDK 프로젝트

이 CDK 프로젝트는 AgentCore CLI에서 관리합니다. `@aws/agentcore-cdk` L3 construct를 사용하여 에이전트 인프라를 AWS에 배포합니다.

## 구조

- `bin/cdk.ts` - 진입점. `agentcore/`에서 프로젝트 구성을 읽고 배포 대상별로 스택을 생성합니다.
- `lib/cdk-stack.ts` - `AgentCoreApplication` L3 construct를 래핑하는 `AgentCoreStack`을 정의합니다.
- `test/cdk.test.ts` - 스택 합성용 단위 테스트입니다.

## 유용한 명령

- `npm run build`: TypeScript를 JavaScript로 컴파일
- `npm run test`: 단위 테스트 실행
- `npx cdk synth`: 합성된 CloudFormation 템플릿 출력
- `npx cdk deploy`: 기본 AWS 계정/리전에 이 스택 배포
- `npx cdk diff`: 배포된 스택과 현재 상태 비교

## 사용법

일반적으로 이 디렉터리와 직접 상호 작용할 필요가 없습니다. AgentCore CLI가 합성과 배포를 처리합니다.

```bash
agentcore deploy    # CDK를 통해 합성 및 배포
agentcore status    # 배포 상태 확인
```

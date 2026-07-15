# 사용 사례

**Amazon Bedrock AgentCore payments**의 실제 동작을 보여 주는 사용 사례입니다. 각 사용 사례는 자체 Notebook, 환경 구성, 지원 인프라를 갖춘 독립 실행형 샘플입니다.

## 사용 가능한 사례

### [콘텐츠 결제(Browser Use)](pay-for-content-browser-use/)

**Strands Agents**와 **AgentCoreBrowser**로 구축한 AI 에이전트가 paywall이 적용된 웹사이트를 자율적으로 탐색하고, 페이지 DOM에서 x402 결제 요구 사항을 읽고, AgentCore payments를 통해 결제한 다음 잠금 해제된 콘텐츠를 반환합니다. 에이전트는 private key를 보유하지 않으며 결제 단계에 사람의 개입이 필요하지 않습니다.

**주요 특징**
- 브라우저 기반 x402 흐름(HTTP 402 가로채기가 아닌 DOM 내장 결제 요구 사항)
- 세션 관리와 결제 실행 간 IAM 역할 분리
- Coinbase CDP를 통한 embedded wallet 프로비저닝
- end-to-end 테스트를 위한 배포 가능한 CDK 콘텐츠 제공업체 스택 포함
- Base Sepolia testnet에서 end-to-end 테스트 완료

---

### [데이터 결제(Heurist)](pay-for-data/)

금융 리서치 에이전트가 실시간 시장 가격, SEC 공시, 거시경제 지표를 제공하는 유료 **Heurist x402 엔드포인트**를 호출하고, **AgentCore Code Interpreter**로 데이터를 분석한 다음 차트와 보고서를 S3 presigned URL로 반환합니다. `AgentCorePaymentsPlugin`이 전체 x402 결제 수명 주기를 처리하므로 도구 코드는 단순한 `http_request` 호출로 유지됩니다.

**주요 특징**
- AgentCorePaymentsPlugin을 통한 HTTP 402 가로채기 및 자동 결제 재시도
- Base mainnet에서 USDC로 결제하는 병렬 유료 도구 호출
- pandas/matplotlib 분석 및 S3 artifact 내보내기를 위한 AgentCore Code Interpreter
- 전체 AgentCore observability를 적용한 AgentCore Runtime 배포

> ⚠️ **Mainnet 샘플.** 이 사용 사례는 Base mainnet에서 실제 USDC로 결제합니다. 실행 전에 embedded wallet에 자금을 충전하세요. 일반적인 호출당 가격은 $0.002~$0.005이며, 1 USDC로 약 200회를 호출할 수 있습니다.

---

### [API 결제](pay-for-api-agent/)

**Strands Agents**로 구축한 AI 에이전트가 AgentCore payments를 통해 HTTP API 사용량 기반 액세스 비용을 자율적으로 결제합니다. 판매자는 AWS CDK로 배포된 "Fun Facts" Amazon API Gateway 및 AWS Lambda 서비스로, 호출당 $0.01를 부과하고 EVM 또는 Solana 결제를 받습니다. 에이전트가 HTTP 402를 받으면 `AgentCorePaymentsPlugin`이 요구 사항을 AgentCore payments로 전달하고 서명된 증명을 첨부한 뒤 다시 시도합니다. 에이전트의 도구 코드는 단순한 `http_request` 호출로 유지됩니다.

**주요 특징**
- `AgentCorePaymentsPlugin`을 통한 HTTP 402 가로채기(브라우저 및 수동 handshake 불필요)
- 멀티 제공업체: 동일한 에이전트 코드가 Coinbase CDP 및 Privy를 통한 Stripe에서 실행
- 멀티 네트워크: testnet의 EVM(Base Sepolia) 및 Solana(Solana Devnet)
- 4개의 IAM 역할로 control plane, 관리, 결제 서명, 자격 증명 검색 간 직무 분리 적용
- 자체 완결형: Notebook에서 AgentCore payments 스택을 인라인으로 프로비저닝하고 포함된 CDK 앱으로 판매자 배포
- CloudWatch Transaction Search 및 GenAI Observability 대시보드를 포함한 AgentCore Runtime 배포

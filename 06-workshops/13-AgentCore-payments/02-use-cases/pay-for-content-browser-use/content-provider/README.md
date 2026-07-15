# 데모 콘텐츠 공급자 - x402 Paywall

x402 v2 protocol을 사용해 유료 콘텐츠를 제공하는 CloudFront + Lambda@Edge
배포입니다. **Pay for Content (Browser)** 사용 사례의 "판매자" 측으로 사용됩니다.

> **참고:** 이 콘텐츠 공급자는 데모이며 샘플 Notebook의 테스트 대상으로만
> 사용됩니다. x402 paywall 검증을 위한 참조 구현이 아닙니다.

## 작동 방식

- paywall 페이지는 HTTP 200으로 로드됩니다. 콘텐츠는 DOM에 표시되지만 UI widget으로 잠겨 있습니다.
- x402 결제 요구 사항이 `<script id="x402-requirement">`에 포함되어 browser agent가
  HTTP header를 파싱하지 않고도 읽을 수 있습니다.
- Lambda@Edge가 올바른 지갑 주소와 가격이 포함된 paywall 페이지를 동적으로 생성합니다.
- 유효한 base64-encoded proof를 제출하면 클라이언트 측에서 콘텐츠 잠금이 해제됩니다.

## 사전 요구 사항

- AWS CLI v2 구성(`aws configure`)
- Node.js 18+
- AWS CDK v2 (`npm install -g aws-cdk`)
- USDC 결제를 받을 판매자 지갑 주소(`0x...`)

## 배포

```bash
cd content-provider
PAY_TO=0x<your-wallet-address> bash deploy.sh
```

`deploy.sh`는 다음 작업을 수행합니다.
1. CDK 종속성 설치(`cdk/`에서 `npm install`)
2. `us-east-1`에서 CDK bootstrap 실행(Lambda@Edge에는 us-east-1이 필요하며 안전하게 다시 실행 가능)
3. CloudFront distribution + Lambda@Edge stack 배포(최초 실행 시 약 5분)
4. 마지막에 CloudFront URL 출력

출력된 URL을 `.env` 파일에 복사합니다.

```
CONTENT_DISTRIBUTION_URL=https://d<id>.cloudfront.net
```

## 선택적 구성

| 변수 | 기본값 | 설명 |
|----------|---------|-------------|
| `PAY_TO` | **필수** | USDC를 받을 판매자 지갑 주소 |
| `PRICE_USDC_UNITS` | `100000` | USDC atomic unit 단위의 가격(소수점 6자리). `100000` = $0.10 USDC |
| `NETWORK` | `eip155:84532` | CAIP-2 network(Base Sepolia testnet) |
| `USDC_ADDRESS` | Base Sepolia USDC | USDC contract 주소 |
| `AWS_PROFILE` | *(기본 프로필)* | 명명된 AWS CLI profile |

값을 재정의하는 예:

```bash
PAY_TO=0xabc... PRICE_USDC_UNITS=100000 bash deploy.sh
```

## 각 사용자의 자체 stack 배포

이 사용 사례의 각 사용자는 자체 CDK stack을 배포합니다. 배포 출력에 표시된
CloudFront URL을 `.env` 파일의 `CONTENT_DISTRIBUTION_URL`에 복사하세요.

```
CONTENT_DISTRIBUTION_URL=https://d<id>.cloudfront.net
```

CDK stack(CloudFront + Lambda@Edge + S3)은 저렴하게 실행할 수 있으며 배포에
약 5분이 걸립니다. 실습을 마치면 `npx cdk destroy`로 제거하세요.

## 로컬 실행(개발 전용)

로컬 개발에는 Express.js server(`index.js`)를 사용할 수 있습니다.

```bash
npm install
PAY_TO=0x<your-wallet-address> npm start
```

server는 `http://localhost:3000`에서 시작됩니다.

**중요:** `AgentCoreBrowser`는 클라우드 관리형 browser이므로 `localhost`에 접근할 수
없습니다. 로컬 모드는 페이지를 검사하고 paywall HTML을 디버깅할 때만 사용하세요.
실제 Notebook 에이전트를 실행할 때는 CDK 배포를 사용해야 합니다.

## 정리

`content-provider/` 디렉터리에서 다음을 실행합니다.

```bash
cd cdk
npx cdk destroy
```

이 명령은 CloudFront distribution, Lambda@Edge function 및 S3 bucket을 제거합니다.
CloudFront distribution이 삭제 후 완전히 비활성화되는 데 약 5분이 걸립니다.

## browser agent에서 사용하는 DOM 요소

browser agent는 이러한 요소를 동적으로 검색합니다. 이 데모 콘텐츠 공급자에서는
ID가 고정되어 있습니다. 사용자 지정 stack을 배포하는 경우 페이지 소스를 확인하세요.

| 요소 ID | 용도 |
|------------|---------|
| `x402-requirement` | JSON 결제 요구 사항을 포함하는 `<script>` |
| `pay-btn` | 결제 흐름을 시작하는 button |
| `proof-input` | base64-encoded proof를 위한 `<textarea>` |
| `verify-btn` | proof를 제출하는 button |
| `content` | 잠금 해제된 기사 텍스트를 포함하는 `<div>` |

**이 요소 ID는 데모 콘텐츠 공급자에서만 사용됩니다.** 실제 x402 site에서는
다른 selector를 사용합니다. 에이전트 system prompt는 hardcoded ID 대신 의미론적
단서(button text, input type, aria-label)를 사용해 결제 요소를 동적으로 찾도록
모델에 지시합니다.

## 아키텍처

```
User / Browser Agent
        │ HTTPS
        ▼
┌─────────────────────────────────┐
│  CloudFront Distribution        │
│                                 │
│  /article/paywall-demo ─────────┼──► Lambda@Edge (viewer-request)
│  (Lambda@Edge behavior)         │    • Generates paywall HTML with
│                                 │      x402 requirement embedded in DOM
│  /* ────────────────────────────┼──► S3 Origin (static assets)
│  (default S3 behavior)          │    • index.html, static files
└─────────────────────────────────┘
```

Lambda@Edge는 CDK 빌드 시 esbuild `--define` flag를 통해 판매자 지갑 주소,
가격 및 network를 삽입합니다. Runtime에는 환경 변수가 필요하지 않습니다.

"""Fun Facts seller CDK stack입니다.

agentcore-payments의 표준 seller 패턴
(backend/lambdas/sellers/crypto-price)을 따릅니다.

  - 미리 설치한 ``node_modules``를 asset에 함께 package하는 Node.js 20 ARM64
    AWS Lambda function입니다(deploy script가 ``cdk deploy`` 전에 ``npm install`` 실행).
  - Payout용 환경 변수 ``SELLER_WALLET_ADDRESS``(EVM/Base Sepolia)와
    ``SELLER_SOLANA_WALLET_ADDRESS``(Solana/Devnet)를 사용합니다. x402 seller
    library가 각 402 응답의 ``accepts`` 배열에 두 값을 전달합니다. 하나만 설정하거나,
    둘 다 설정하거나, 모두 설정하지 않을 수 있으며 Lambda는 구성된 network마다
    하나의 ``accepts`` 항목을 내보냅니다.
  - ``X402_FACILITATOR_URL``로 private facilitator를 가리키도록 재정의할 수 있습니다.
    기본값은 public x402.org facilitator입니다.
  - x402 payment middleware로 보호되는 ``GET /facts`` route 하나와 상태 확인용
    public ``GET /`` 및 ``GET /health`` route를 제공합니다.
"""

from __future__ import annotations

import os
from pathlib import Path

from aws_cdk import (
    CfnOutput,
    Duration,
    Stack,
)
from aws_cdk import aws_apigatewayv2 as apigwv2
from aws_cdk import aws_apigatewayv2_integrations as apigwv2_integrations
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_logs as logs
from constructs import Construct

LAMBDA_CODE_DIR = str(Path(__file__).resolve().parent.parent / "lambda")


class AgentCorePaymentsFunFactsSellerStack(Stack):
    """최소 구성의 x402 seller인 HTTP API -> Node.js Lambda를 구성합니다."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── Seller config ────────────────────────────────────────────
        # 배포 시 CDK context(`cdk deploy -c seller_wallet=0x…`) 또는 환경 변수로
        # 재정의합니다. 두 network 모두 선택 사항입니다. 둘 다 설정하지 않아도
        # Lambda는 실행되지만 facilitator가 payment proof를 거부하므로 하나 이상
        # 설정하세요.
        #
        # 설정되지 않은 wallet이 빈 문자열이 아닌 명확한 invalid placeholder로
        # 표시되도록 기본값은 "WALLET_NOT_CONFIGURED"입니다
        # (seller/lambda/index.js와 동일).
        evm_wallet = (
            self.node.try_get_context("seller_wallet")
            or os.environ.get("SELLER_WALLET_ADDRESS")
            or "WALLET_NOT_CONFIGURED"
        )
        solana_wallet = (
            self.node.try_get_context("seller_solana_wallet")
            or os.environ.get("SELLER_SOLANA_WALLET_ADDRESS")
            or "WALLET_NOT_CONFIGURED"
        )
        facilitator_url = os.environ.get("X402_FACILITATOR_URL") or "https://x402.org/facilitator"
        price = os.environ.get("X402_PRICE") or "$0.01"

        # ── Lambda function ──────────────────────────────────────────
        seller_fn = _lambda.Function(
            self,
            "SellerFunction",
            runtime=_lambda.Runtime.NODEJS_20_X,
            architecture=_lambda.Architecture.ARM_64,
            handler="index.handler",
            # Deploy script는 `cdk deploy` 전에 lambda/ 폴더에서 `npm install`을
            # 실행하므로 asset에 node_modules가 함께 포함됩니다. agentcore-payments
            # seller에서 사용하는 패턴과 같습니다.
            code=_lambda.Code.from_asset(LAMBDA_CODE_DIR),
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "SELLER_WALLET_ADDRESS": evm_wallet,
                "SELLER_SOLANA_WALLET_ADDRESS": solana_wallet,
                "X402_FACILITATOR_URL": facilitator_url,
                "X402_PRICE": price,
            },
            log_retention=logs.RetentionDays.ONE_WEEK,
            description="Fun Facts x402 seller — AgentCore Payments use case",
        )

        # ── HTTP API ─────────────────────────────────────────────────
        # 데모에서는 모든 호출자(AgentCore Runtime 컨테이너, browser 기반 debugger,
        # curl session)가 seller에 접근할 수 있도록 CORS를 완전히 개방합니다.
        # Production에서는 이 seller를 호출해야 하는 특정 agent runtime endpoint로
        # origin을 제한하고 method를 GET 및 OPTIONS로 제한하세요.
        http_api = apigwv2.HttpApi(
            self,
            "SellerHttpApi",
            api_name="pay-for-api-fun-facts",
            description="Fun Facts x402 seller — pay-per-fact via x402",
            cors_preflight=apigwv2.CorsPreflightOptions(
                # 데모 구성입니다. Production에서는 특정 origin(예: agent runtime
                # domain)으로 제한하세요.
                allow_origins=["*"],
                allow_methods=[apigwv2.CorsHttpMethod.ANY],
                allow_headers=["*"],
            ),
        )

        integration = apigwv2_integrations.HttpLambdaIntegration(
            "SellerLambdaIntegration",
            handler=seller_fn,
        )

        # 단일 proxy route가 GET /, GET /facts, GET /health를 처리합니다.
        http_api.add_routes(
            path="/{proxy+}",
            methods=[apigwv2.HttpMethod.ANY],
            integration=integration,
        )
        http_api.add_routes(
            path="/",
            methods=[apigwv2.HttpMethod.ANY],
            integration=integration,
        )

        # ── 출력 ──────────────────────────────────────────────────────
        CfnOutput(
            self,
            "SellerApiUrl",
            value=http_api.api_endpoint,
            description="Invoke URL for the Fun Facts x402 seller API",
        )
        CfnOutput(
            self,
            "SellerEvmWallet",
            value=evm_wallet or "(unset)",
            description=(
                "EVM (Base Sepolia) wallet that receives USDC for paid "
                "requests. Set via `cdk deploy -c seller_wallet=0x…` or "
                "the SELLER_WALLET_ADDRESS env var."
            ),
        )
        CfnOutput(
            self,
            "SellerSolanaWallet",
            value=solana_wallet or "(unset)",
            description=(
                "Solana (Devnet) wallet that receives USDC for paid "
                "requests. Set via `cdk deploy -c seller_solana_wallet=…` "
                "or the SELLER_SOLANA_WALLET_ADDRESS env var."
            ),
        )

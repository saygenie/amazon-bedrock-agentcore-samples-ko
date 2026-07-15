"""
보험 인수용 Lambda 대상을 포함하는 Gateway 생성 설정 스크립트
deploy_lambdas.py로 Lambda 함수를 배포한 후 실행합니다.
"""

import json
import logging
import sys
import time
import boto3
from pathlib import Path
from bedrock_agentcore_starter_toolkit.operations.gateway.client import GatewayClient

GATEWAY_NAME = "GW-Insurance-Underwriting"


def _find_gateway_by_name(region: str) -> str | None:
    """GATEWAY_NAME과 같은 Gateway가 이미 있으면 해당 ID를 반환합니다."""
    client = boto3.client("bedrock-agentcore-control", region_name=region)
    try:
        resp = client.list_gateways()
        for gw in resp.get("items", []):
            if gw.get("name") == GATEWAY_NAME and gw.get("status") in [
                "READY",
                "ACTIVE",
            ]:
                return gw["gatewayId"]
    except Exception:
        pass
    return None


def _delete_gateway(region: str, gateway_id: str) -> None:
    """모든 대상을 삭제하고 대상이 정리될 때까지 기다린 후 Gateway를 삭제합니다."""
    client = boto3.client("bedrock-agentcore-control", region_name=region)
    try:
        targets = client.list_gateway_targets(gatewayIdentifier=gateway_id).get("items", [])
        for t in targets:
            client.delete_gateway_target(gatewayIdentifier=gateway_id, targetId=t["targetId"])
        # 삭제는 비동기로 진행되므로 모든 대상이 사라질 때까지 대기
        for _ in range(30):
            remaining = client.list_gateway_targets(gatewayIdentifier=gateway_id).get("items", [])
            if not remaining:
                break
            time.sleep(3)
        client.delete_gateway(gatewayIdentifier=gateway_id)
        print(f"   Deleted stale gateway and {len(targets)} target(s): {gateway_id}")
        time.sleep(5)
    except Exception as exc:
        print(f"   Warning: could not delete gateway {gateway_id}: {exc}")


def load_config():
    """기존 config.json을 로드합니다."""
    config_file = Path(__file__).parent.parent / "config.json"

    if not config_file.exists():
        print("❌ Error: config.json not found!")
        print(f"   Expected location: {config_file}")
        print("\n   Please run deploy_lambdas.py first to create Lambda functions")
        sys.exit(1)

    try:
        with open(config_file, "r", encoding="utf-8") as f:
            return json.load(f), config_file
    except Exception as exc:
        print(f"❌ Error reading config.json: {exc}")
        sys.exit(1)


def setup_gateway():
    """보험 인수용 Lambda 대상을 포함하는 AgentCore Gateway를 설정합니다."""

    print("🚀 Setting up AgentCore Gateway for Insurance Underwriting...\n")

    # 기존 구성 로드(deploy_lambdas.py에서 설정한 리전 포함)
    print("📦 Loading configuration...")
    existing_config, config_file = load_config()

    region = existing_config.get("region")
    if not region:
        raise ValueError("Region not found in config.json. Please run deploy_lambdas.py first.")

    print(f"Region: {region}\n")

    # --- 멱등성: 구성이 완전하면 기존 Gateway 재사용 ----------------------
    saved_gateway = existing_config.get("gateway", {})
    saved_gw_id = saved_gateway.get("gateway_id")
    if saved_gw_id:
        boto_ctrl = boto3.client("bedrock-agentcore-control", region_name=region)
        try:
            gw_status = boto_ctrl.get_gateway(gatewayIdentifier=saved_gw_id).get("status")
            if gw_status in ("READY", "ACTIVE"):
                print(f"✅ Reusing existing gateway from config: {saved_gw_id}")
                print(f"   Gateway URL: {saved_gateway.get('gateway_url')}")
                print("=" * 70)
                return existing_config
        except Exception:
            print(f"   Gateway {saved_gw_id} not found in AWS — will create fresh.")

    # --- 구성이 없으면 이름으로 오래된 Gateway를 찾아 제거 ----------------
    stale_id = _find_gateway_by_name(region)
    if stale_id:
        print(f"⚠️  Found stale gateway '{GATEWAY_NAME}' ({stale_id}) with no saved config.")
        print("   Deleting it so a fresh one can be created...")
        _delete_gateway(region, stale_id)
    # -----------------------------------------------------------------------

    lambda_config = existing_config.get("lambdas", {})

    if not lambda_config:
        print("❌ No Lambda functions found in config.json")
        sys.exit(1)

    print("✅ Found Lambda functions:")
    for name, arn in lambda_config.items():
        print(f"   • {name}: {arn}")
    print()

    # 클라이언트 초기화
    print("� Iniutializing AgentCore client...")
    client = GatewayClient(region_name=region)
    client.logger.setLevel(logging.INFO)

    # 1단계: OAuth 권한 부여자 생성
    print("\n📝 Step 1: Creating OAuth authorization server...")
    cognito_response = client.create_oauth_authorizer_with_cognito("InsuranceUnderwritingGateway")
    print("✅ Authorization server created")

    # 2단계: Gateway 생성(역할은 자동 생성)
    print("\n📝 Step 2: Creating AgentCore Gateway...")
    gateway = client.create_mcp_gateway(
        name=GATEWAY_NAME,
        role_arn=None,  # 툴킷에서 역할 생성
        authorizer_config=cognito_response["authorizer_config"],
        enable_semantic_search=True,
    )
    print(f"✅ Gateway created: {gateway['gatewayUrl']}")

    # 자동 생성된 역할의 IAM 권한 수정
    print("\n📝 Step 2.1: Configuring IAM permissions...")
    client.fix_iam_permissions(gateway)
    print("⏳ Waiting 30s for IAM propagation...")
    time.sleep(30)
    print("✅ IAM permissions configured")

    # 3단계: Lambda 대상 추가
    print("\n📝 Step 3: Adding Lambda targets...")

    # 스키마와 함께 Lambda 함수 정의
    lambda_functions = []

    # ApplicationTool - 1단계: 신청서 제출
    if "ApplicationTool" in lambda_config:
        lambda_functions.append(
            {
                "name": "ApplicationTool",
                "arn": lambda_config["ApplicationTool"],
                "schema": [
                    {
                        "name": "create_application",
                        "description": "Create insurance application with geographic and eligibility validation",
                        "inputSchema": {
                            "type": "object",
                            "description": "Input parameters for insurance application creation",
                            "properties": {
                                "applicant_region": {
                                    "type": "string",
                                    "description": "Customer's geographic region (US, CA, UK, EU, APAC, etc.)",
                                },
                                "coverage_amount": {
                                    "type": "integer",
                                    "description": "Requested insurance coverage amount",
                                },
                            },
                            "required": ["applicant_region", "coverage_amount"],
                        },
                    }
                ],
            }
        )

    # RiskModelTool - 3단계: 외부 점수 산정 통합
    if "RiskModelTool" in lambda_config:
        lambda_functions.append(
            {
                "name": "RiskModelTool",
                "arn": lambda_config["RiskModelTool"],
                "schema": [
                    {
                        "name": "invoke_risk_model",
                        "description": "Invoke external risk scoring model with governance controls",
                        "inputSchema": {
                            "type": "object",
                            "description": "Input parameters for risk model invocation",
                            "properties": {
                                "API_classification": {
                                    "type": "string",
                                    "description": "API classification (public, internal, restricted)",
                                },
                                "data_governance_approval": {
                                    "type": "boolean",
                                    "description": "Whether data governance has approved model usage",
                                },
                            },
                            "required": [
                                "API_classification",
                                "data_governance_approval",
                            ],
                        },
                    }
                ],
            }
        )

    # ApprovalTool - 7단계: 상급자 승인
    if "ApprovalTool" in lambda_config:
        lambda_functions.append(
            {
                "name": "ApprovalTool",
                "arn": lambda_config["ApprovalTool"],
                "schema": [
                    {
                        "name": "approve_underwriting",
                        "description": "Approve high-value or high-risk underwriting decisions",
                        "inputSchema": {
                            "type": "object",
                            "description": "Input parameters for underwriting approval",
                            "properties": {
                                "claim_amount": {
                                    "type": "integer",
                                    "description": "Insurance claim/coverage amount",
                                },
                                "risk_level": {
                                    "type": "string",
                                    "description": "Risk level assessment (low, medium, high, critical)",
                                },
                            },
                            "required": ["claim_amount", "risk_level"],
                        },
                    }
                ],
            }
        )

    # 각 Lambda 대상을 Gateway에 추가
    gateway_arn = None
    for lambda_func in lambda_functions:
        print(f"\n   🔧 Adding {lambda_func['name']} target...")

        try:
            target = client.create_mcp_gateway_target(
                gateway=gateway,
                name=f"{lambda_func['name']}Target",
                target_type="lambda",
                target_payload={
                    "lambdaArn": lambda_func["arn"],
                    "toolSchema": {"inlinePayload": lambda_func["schema"]},
                },
                credentials=None,
            )

            if gateway_arn is None:
                gateway_arn = target.get("gatewayArn")

            print(f"   ✅ Successfully added {lambda_func['name']} target")

        except Exception as e:
            print(f"   ❌ Error adding {lambda_func['name']} target: {e}")

    # 4단계: 기존 config.json에 Gateway 정보 업데이트
    print("\n📝 Step 4: Updating config.json with gateway information...")

    # 기존 구성에 Gateway 구성 추가
    existing_config["gateway"] = {
        "gateway_url": gateway["gatewayUrl"],
        "gateway_id": gateway["gatewayId"],
        "gateway_arn": gateway_arn or gateway.get("gatewayArn"),
        "gateway_name": GATEWAY_NAME,
        "client_info": cognito_response["client_info"],
    }

    # 업데이트된 구성을 config.json에 다시 쓰기
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(existing_config, f, indent=2)

    print("\n" + "=" * 70)
    print("✅ GATEWAY SETUP COMPLETE!")
    print("=" * 70)
    print("Gateway Name: GW-Insurance-Underwriting")
    print(f"Gateway URL: {gateway['gatewayUrl']}")
    print(f"Gateway ID: {gateway['gatewayId']}")
    print(f"Gateway ARN: {existing_config['gateway']['gateway_arn']}")
    print(f"\nTargets Added: {len(lambda_functions)}")
    for func in lambda_functions:
        print(f"   • {func['name']}")
    print(f"\nConfiguration updated in: {config_file}")
    print("=" * 70)

    return existing_config


if __name__ == "__main__":
    setup_gateway()

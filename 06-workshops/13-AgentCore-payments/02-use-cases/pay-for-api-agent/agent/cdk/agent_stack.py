"""Pay for API - buyer agent CDK stack입니다.

``cdk deploy``를 실행하는 장비에 Docker가 없어도 buyer agent용 전체
AgentCore Runtime stack을 provisioning합니다.

1. **Amazon S3 asset** - ``agent/container/``를 압축해 CDK bootstrap asset
   bucket에 업로드합니다.
2. **Amazon ECR repository** - build한 image의 대상입니다.
3. **AWS CodeBuild project** - S3 asset을 가져와 ``docker build``를 실행하고
   ECR로 push하는 ARM64 Linux 환경입니다. AWS에서 실행되므로 호출자에게는
   ``cdk deploy``와 AWS credential만 필요합니다.
4. **Build trigger AWS Lambda function** - CodeBuild 실행을 시작하고 Runtime
   resource를 생성하기 전에 image가 ECR에 들어갈 때까지 polling하는 custom
   resource입니다.
5. **IAM execution role** - 호출 시 runtime에 필요한 최소 권한(Amazon Bedrock,
   AgentCore Payments data plane, Amazon CloudWatch Logs, AWS X-Ray,
   Amazon CloudWatch Application Signals, vended log delivery)을 제공합니다.
6. **AgentCore Runtime** - 새로 build한 image를 가리킵니다.

Notebook이 배포된 agent를 이름으로 호출할 수 있도록 Runtime ARN, 호출 URL,
execution role ARN을 출력합니다.
"""

from __future__ import annotations

from pathlib import Path

from aws_cdk import (
    CfnOutput,
    CustomResource,
    Duration,
    RemovalPolicy,
    Stack,
    aws_bedrockagentcore as bedrockagentcore,
    aws_codebuild as codebuild,
    aws_ecr as ecr,
    aws_iam as iam,
    aws_lambda as aws_lambda,
    aws_s3_assets as s3_assets,
)
from constructs import Construct

# 컨테이너 source는 cdk/와 같은 상위 폴더 아래에 있으므로 S3 asset과 docker
# build가 동일한 context를 공유하도록 absolute path를 한 번 확인합니다.
CONTAINER_DIR = str(Path(__file__).resolve().parent.parent / "container")


class AgentCorePaymentsBuyerAgentStack(Stack):
    """Pay for API buyer agent용 AgentCore Runtime과 IAM을 구성합니다."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── ECR repository ──
        agent_repo = ecr.Repository(
            self,
            "AgentEcrRepo",
            repository_name="pay-for-api-agent",
            removal_policy=RemovalPolicy.DESTROY,
            empty_on_delete=True,
            lifecycle_rules=[
                ecr.LifecycleRule(
                    max_image_count=5,
                    description="Keep the 5 most recent images",
                )
            ],
        )

        # ── S3 asset: agent/container/ 압축 파일 ──
        # CDK는 `cdk deploy` 때마다 이를 bootstrap asset bucket에 업로드합니다.
        # CodeBuild가 S3에서 가져오므로 GitHub, CodeCommit, 로컬 Docker가
        # 필요하지 않습니다.
        agent_source = s3_assets.Asset(
            self,
            "AgentSourceAsset",
            path=CONTAINER_DIR,
        )

        # ── CodeBuild project ──
        build_project = codebuild.Project(
            self,
            "AgentBuildProject",
            project_name="pay-for-api-agent-build",
            environment=codebuild.BuildEnvironment(
                # ARM64는 AgentCore Runtime의 Graviton host와 일치합니다.
                build_image=codebuild.LinuxArmBuildImage.AMAZON_LINUX_2_STANDARD_3_0,
                compute_type=codebuild.ComputeType.SMALL,
                privileged=True,  # image build를 위한 docker-in-docker
            ),
            source=codebuild.Source.s3(
                bucket=agent_source.bucket,
                path=agent_source.s3_object_key,
            ),
            environment_variables={
                "AWS_ACCOUNT_ID": codebuild.BuildEnvironmentVariable(value=self.account),
                "AWS_DEFAULT_REGION": codebuild.BuildEnvironmentVariable(value=self.region),
                "ECR_REPO_URI": codebuild.BuildEnvironmentVariable(value=agent_repo.repository_uri),
                "IMAGE_TAG": codebuild.BuildEnvironmentVariable(value=agent_source.asset_hash),
            },
            build_spec=codebuild.BuildSpec.from_object(
                {
                    "version": "0.2",
                    "phases": {
                        "pre_build": {
                            "commands": [
                                "echo Logging in to ECR...",
                                "aws ecr get-login-password --region $AWS_DEFAULT_REGION | "
                                "docker login --username AWS --password-stdin "
                                "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com",
                            ],
                        },
                        "build": {
                            "commands": [
                                "echo Building agent image...",
                                "docker build -t $ECR_REPO_URI:$IMAGE_TAG .",
                            ],
                        },
                        "post_build": {
                            "commands": [
                                "echo Pushing to ECR...",
                                "docker push $ECR_REPO_URI:$IMAGE_TAG",
                                "docker tag $ECR_REPO_URI:$IMAGE_TAG $ECR_REPO_URI:latest",
                                "docker push $ECR_REPO_URI:latest",
                            ],
                        },
                    },
                }
            ),
        )
        agent_repo.grant_pull_push(build_project)

        # ── Custom resource: build를 시작하고 완료될 때까지 대기 ──
        # 아래 Runtime resource가 image URI를 참조하므로 CloudFormation이 이
        # 단계를 지나기 전에 ECR에 image가 있어야 합니다.
        build_trigger_role = iam.Role(
            self,
            "BuildTriggerRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"),
            ],
        )
        build_trigger_role.add_to_policy(
            iam.PolicyStatement(
                actions=["codebuild:StartBuild", "codebuild:BatchGetBuilds"],
                resources=[build_project.project_arn],
            )
        )

        build_trigger_fn = aws_lambda.Function(
            self,
            "BuildTriggerFn",
            function_name="pay-for-api-agent-build-trigger",
            runtime=aws_lambda.Runtime.PYTHON_3_12,
            handler="index.handler",
            role=build_trigger_role,
            timeout=Duration.minutes(15),
            memory_size=128,
            code=aws_lambda.Code.from_inline(
                r"""
import json
import time
import urllib.request

import boto3


def handler(event, context):
    props = event.get("ResourceProperties", {})
    project_name = props.get("ProjectName", "")

    # No rebuild on stack delete — ECR contents are torn down by the
    # repository's lifecycle.
    if event["RequestType"] == "Delete":
        return _respond(event, context, "SUCCESS", {"ImageBuilt": "skipped"})

    cb = boto3.client("codebuild")
    try:
        build = cb.start_build(projectName=project_name)
        build_id = build["build"]["id"]
        print(f"Started CodeBuild: {build_id}")

        # Poll every 30 seconds for up to ~14 minutes.
        for _ in range(28):
            time.sleep(30)
            result = cb.batch_get_builds(ids=[build_id])
            status = result["builds"][0]["buildStatus"]
            print(f"Build status: {status}")
            if status == "SUCCEEDED":
                return _respond(event, context, "SUCCESS", {"BuildId": build_id})
            if status in ("FAILED", "FAULT", "STOPPED", "TIMED_OUT"):
                return _respond(
                    event, context, "FAILED",
                    {"Error": f"CodeBuild {status}"},
                )
        return _respond(event, context, "FAILED", {"Error": "Build timed out"})
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}")
        return _respond(event, context, "FAILED", {"Error": str(exc)})


def _respond(event, context, status, data):
    body = json.dumps({
        "Status": status,
        "Reason": json.dumps(data),
        "PhysicalResourceId": context.log_stream_name,
        "StackId": event["StackId"],
        "RequestId": event["RequestId"],
        "LogicalResourceId": event["LogicalResourceId"],
        "Data": data,
    })
    req = urllib.request.Request(
        event["ResponseURL"],
        data=body.encode(),
        method="PUT",
        headers={"Content-Type": ""},
    )
    urllib.request.urlopen(req)
"""
            ),
        )

        trigger_build = CustomResource(
            self,
            "TriggerImageBuild",
            service_token=build_trigger_fn.function_arn,
            properties={
                "ProjectName": build_project.project_name,
                # CR hash를 asset hash에 연결해 agent/container/가 변경되면
                # 자동으로 다시 build합니다.
                "SourceHash": agent_source.asset_hash,
            },
        )

        # ── IAM: runtime execution role ──
        execution_role = iam.Role(
            self,
            "AgentExecutionRole",
            assumed_by=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            description=(
                "Pay for API buyer agent runtime execution role. "
                "Grants Bedrock model invoke + AgentCore Payments DP ops the "
                "AgentCorePaymentsPlugin needs at runtime."
            ),
        )

        # Bedrock model 호출 - US cross-region inference profile을 통해
        # Claude Sonnet 4.5를 사용합니다. Bedrock가 profile을 통해 확인하므로
        # foundation model ARN과 inference profile ARN 모두에 권한을 부여합니다.
        execution_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                ],
                resources=[
                    # Inference profile(cross-region routing)
                    f"arn:aws:bedrock:{self.region}:{self.account}:inference-profile/us.anthropic.claude-sonnet-4-5-20250929-v1:0",
                    # Profile이 route할 수 있는 각 US region의 기반 foundation model
                    "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-sonnet-4-5-20250929-v1:0",
                    "arn:aws:bedrock:us-east-2::foundation-model/anthropic.claude-sonnet-4-5-20250929-v1:0",
                    "arn:aws:bedrock:us-west-2::foundation-model/anthropic.claude-sonnet-4-5-20250929-v1:0",
                ],
            )
        )

        # Plugin이 runtime에 호출하는 AgentCore Payments data plane 작업입니다.
        # Role 생성 시점에는 Manager/Instrument/Session ID를 알 수 없으므로
        # (Notebook이 4절에서 생성) resource 목록은 호출자 account의 모든
        # PaymentManager를 wildcard로 지정합니다. Production에서는 값이 안정된 뒤
        # 특정 Manager ARN으로 범위를 제한하거나 `aws:ResourceTag/Project`에
        # tag 기반 condition을 추가하세요.
        execution_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock-agentcore:ProcessPayment",
                    "bedrock-agentcore:GetPaymentSession",
                    "bedrock-agentcore:GetPaymentInstrument",
                    "bedrock-agentcore:GetPaymentInstrumentBalance",
                    "bedrock-agentcore:GetResourcePaymentToken",
                ],
                resources=[
                    f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:payment-manager/*",
                    f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:payment-manager/*/instrument/*",
                    f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:payment-manager/*/session/*",
                ],
            )
        )

        # CloudWatch Logs - Runtime은 role이 자체 log stream을 쓸 수 있어야 합니다.
        execution_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "logs:DescribeLogGroups",
                    "logs:DescribeLogStreams",
                ],
                resources=[
                    f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/bedrock-agentcore/*",
                ],
            )
        )

        # ── Observability ──
        # Agent 컨테이너는 AWS Distro for OpenTelemetry를 실행하고 첫 호출에서
        # PaymentManager의 CloudWatch Logs vended delivery도 연결합니다
        # (agent.py의 `_ensure_vended_log_delivery` 참조). 두 경로 모두 아래
        # 권한이 필요합니다.

        # Log vended delivery pipeline: Payments -> CloudWatch Logs.
        # Delivery source/destination/delivery object는 resource 범위가 아닙니다
        # (CloudWatch Logs가 region 및 account별로 생성). 따라서 resource 목록은
        # wildcard로 유지합니다. Log group 쓰기 자체는 agentcore-payments log group
        # 접두사로 범위가 제한됩니다.
        execution_role.add_to_policy(
            iam.PolicyStatement(
                sid="CloudWatchLogsVendedDelivery",
                actions=[
                    "logs:CreateDelivery",
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:DeleteDelivery",
                    "logs:DeleteDeliveryDestination",
                    "logs:DeleteDeliverySource",
                    "logs:DeleteLogGroup",
                    "logs:DeleteResourcePolicy",
                    "logs:DescribeLogGroups",
                    "logs:DescribeResourcePolicies",
                    "logs:GetDelivery",
                    "logs:GetDeliveryDestination",
                    "logs:GetDeliverySource",
                    "logs:PutDeliveryDestination",
                    "logs:PutDeliverySource",
                    "logs:PutLogEvents",
                    "logs:PutResourcePolicy",
                    "logs:PutRetentionPolicy",
                ],
                # CloudWatch Logs는 Describe* 및 Put*Delivery* API에서 resource
                # 수준 범위 지정을 허용하지 않습니다. Log group 작업은
                # DeliveryDestination으로 제한한 delivery target에 의해 암묵적으로
                # 범위가 정해집니다. Production에서는 값이 안정된 뒤 특정 log group
                # 접두사로 범위를 제한하세요.
                resources=["*"],
            )
        )

        # X-Ray + CloudWatch Application Signals - ADOT 전송 대상입니다.
        # X-Ray와 Application Signals는 이 작업에 resource 수준 ARN을 허용하지
        # 않으며, 문서화된 ADOT observability IAM policy는 Resource: "*"를
        # 사용합니다. Agent trace의 범위는 IAM이 아니라 OpenTelemetry context를
        # 통해 자체 session으로 암묵적으로 제한됩니다.
        execution_role.add_to_policy(
            iam.PolicyStatement(
                sid="XRayApplicationSignalsCloudTrail",
                actions=[
                    "xray:GetTraceSegmentDestination",
                    "xray:ListResourcePolicies",
                    "xray:PutResourcePolicy",
                    "xray:PutTelemetryRecords",
                    "xray:PutTraceSegments",
                    "xray:UpdateTraceSegmentDestination",
                    "application-signals:StartDiscovery",
                    "cloudtrail:CreateServiceLinkedChannel",
                ],
                resources=["*"],
            )
        )

        # Application Signals용 service-linked role입니다. Account마다 한 번
        # 생성되며 condition으로 해당 SLR에 범위를 제한합니다.
        execution_role.add_to_policy(
            iam.PolicyStatement(
                sid="CreateServiceLinkedRoleForAppSignals",
                actions=["iam:CreateServiceLinkedRole"],
                resources=[
                    "arn:*:iam::*:role/aws-service-role/"
                    "application-signals.cloudwatch.amazonaws.com/"
                    "AWSServiceRoleForCloudWatchApplicationSignals",
                ],
            )
        )

        # PaymentManager의 PaymentsAllowVendedLogDeliveryForResource 및
        # AllowVendedLogDeliveryForResource는 Payments가 위의 vended pipeline을
        # 통해 log를 내보낼 수 있게 합니다. Payment Manager ARN을 대상으로
        # `logs.put_delivery_source`를 실행할 때 CloudWatch는 두 작업을 암묵적으로
        # 확인합니다. Payments 접두사가 있는 작업은 product 수준 gate이고, 접두사가
        # 없는 작업은 AgentCore 전체 gate입니다. PaymentManager resource로만
        # 범위를 제한합니다.
        execution_role.add_to_policy(
            iam.PolicyStatement(
                sid="BedrockAgentCorePaymentsVendedLogDelivery",
                actions=[
                    "bedrock-agentcore:PaymentsAllowVendedLogDeliveryForResource",
                    "bedrock-agentcore:AllowVendedLogDeliveryForResource",
                ],
                resources=[
                    f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:payment-manager/*",
                ],
            )
        )

        # ECR pull - runtime이 위에서 build한 image를 가져옵니다.
        agent_repo.grant_pull(execution_role)

        # 이 role을 bedrock-agentcore.amazonaws.com에 전달하도록 허용합니다.
        execution_role.add_to_policy(
            iam.PolicyStatement(
                actions=["iam:PassRole"],
                resources=[execution_role.role_arn],
                conditions={"StringEquals": {"iam:PassedToService": "bedrock-agentcore.amazonaws.com"}},
            )
        )

        # ── AgentCore Memory ──
        # Buyer agent용 영구 conversation Memory입니다. 이 데모는 Notebook 실행
        # 사이에 상태를 유지하지 않으므로 event 만료 기간이 짧습니다. 실제
        # workload에서는 30일 이상으로 늘리세요.
        agent_memory = bedrockagentcore.CfnMemory(
            self,
            "AgentMemory",
            name="pay_for_api_agent_memory",
            description=(
                "Conversation memory for the Pay for API buyer agent. "
                "Each invocation gets its own session under the caller's "
                "paymentUserId actor."
            ),
            event_expiry_duration=7,
        )

        # 호출 시 필요한 Memory CRUD 작업을 runtime role에 부여합니다. 방금 생성한
        # Memory resource로 범위를 제한합니다.
        execution_role.add_to_policy(
            iam.PolicyStatement(
                sid="AgentCoreMemoryCRUD",
                actions=[
                    "bedrock-agentcore:CreateMemory",
                    "bedrock-agentcore:GetMemory",
                    "bedrock-agentcore:UpdateMemory",
                    "bedrock-agentcore:DeleteMemory",
                    "bedrock-agentcore:CreateMemoryRecord",
                    "bedrock-agentcore:GetMemoryRecord",
                    "bedrock-agentcore:UpdateMemoryRecord",
                    "bedrock-agentcore:ListMemoryRecords",
                    "bedrock-agentcore:SearchMemoryRecords",
                    "bedrock-agentcore:DeleteMemoryRecord",
                    "bedrock-agentcore:CreateEvent",
                    "bedrock-agentcore:ListEvents",
                    "bedrock-agentcore:GetEvent",
                    "bedrock-agentcore:DeleteEvent",
                    "bedrock-agentcore:ListActors",
                    "bedrock-agentcore:ListSessions",
                ],
                resources=[
                    f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:memory/*",
                ],
            )
        )

        # ── AgentCore Runtime ──
        # containerUri는 CodeBuild에서 build한 image를 가리킵니다. asset_hash를
        # tag로 사용하므로 agent/container/가 변경되면 새 image를 만들고 Runtime
        # 업데이트를 시작합니다.
        #
        # networkMode=PUBLIC: runtime 컨테이너에 outbound internet 액세스가 있으며
        # agent는 이를 사용해 seller의 HTTP API를 호출합니다. Private service와
        # 통합하는 production 배포에서는 VPC mode로 전환하고 AWS API용 VPC
        # endpoint와 NAT Gateway를 통해 runtime을 route하세요.
        runtime = bedrockagentcore.CfnRuntime(
            self,
            "AgentRuntime",
            agent_runtime_name="pay_for_api_agent_runtime",
            description=(
                "Pay for API buyer agent — Strands Agent with Claude Sonnet "
                "4.5 and AgentCorePaymentsPlugin for autonomous x402 payment."
            ),
            role_arn=execution_role.role_arn,
            network_configuration={"networkMode": "PUBLIC"},
            protocol_configuration="HTTP",
            agent_runtime_artifact={
                "containerConfiguration": {
                    "containerUri": f"{agent_repo.repository_uri}:{agent_source.asset_hash}",
                },
            },
            environment_variables={
                "AWS_REGION": self.region,
                "MODEL_ID": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
                "ENABLE_PAYMENTS_PLUGIN": "1",
                # 첫 호출에서 agent.py의 vended log delivery 연결을 활성화합니다.
                # 디버깅할 때는 "0"으로 설정하세요.
                "ENABLE_VENDED_LOG_DELIVERY": "1",
                # Agent가 agent.py의 AgentCoreMemorySessionManager를 통해 연결하는
                # AgentCore Memory resource입니다.
                "BEDROCK_AGENTCORE_MEMORY_ID": agent_memory.attr_memory_id,
                # ADOT 자동 계측입니다. agent.py의 기본값과 일치하므로
                # opentelemetry-instrument에서도 이 값을 선택합니다.
                "AGENT_OBSERVABILITY_ENABLED": "true",
                "OTEL_PYTHON_DISTRO": "aws_distro",
                "OTEL_PYTHON_CONFIGURATOR": "aws_configurator",
                "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
                "OTEL_TRACES_EXPORTER": "otlp",
                "OTEL_LOGS_EXPORTER": "otlp",
                "OTEL_METRICS_EXPORTER": "none",
            },
        )

        # Runtime은 CodeBuild에서 build한 image가 준비될 때까지 기다려야 합니다.
        runtime.node.add_dependency(trigger_build)
        # 환경 변수를 확인할 수 있도록 Memory resource 생성도 기다립니다.
        runtime.node.add_dependency(agent_memory)

        # ── 출력 ──
        CfnOutput(
            self,
            "AgentRuntimeArn",
            value=runtime.attr_agent_runtime_arn,
            description="ARN of the deployed AgentCore Runtime",
        )
        CfnOutput(
            self,
            "AgentRuntimeId",
            value=runtime.attr_agent_runtime_id,
            description="ID of the deployed AgentCore Runtime",
        )
        CfnOutput(
            self,
            "AgentRuntimeEndpoint",
            # 배포 시 확인됩니다. CloudFormation이 값을 확인하기 전에 CDK f-string이
            # {region} 및 {runtime_id} placeholder를 AgentCore endpoint template에
            # 대입합니다.
            value=(
                f"https://bedrock-agentcore.{self.region}.amazonaws.com/"
                f"runtimes/{runtime.attr_agent_runtime_id}/invocations"
            ),
            description="Invoke URL for the deployed Runtime",
        )
        CfnOutput(
            self,
            "AgentExecutionRoleArn",
            value=execution_role.role_arn,
            description="IAM role the Runtime assumes at invoke time",
        )
        CfnOutput(
            self,
            "AgentEcrRepoUri",
            value=agent_repo.repository_uri,
            description="ECR repository URI the Runtime pulls from",
        )
        CfnOutput(
            self,
            "AgentBuildProjectName",
            value=build_project.project_name,
            description="CodeBuild project that builds the agent image",
        )
        CfnOutput(
            self,
            "AgentMemoryId",
            value=agent_memory.attr_memory_id,
            description="AgentCore Memory resource the runtime uses for sessions",
        )

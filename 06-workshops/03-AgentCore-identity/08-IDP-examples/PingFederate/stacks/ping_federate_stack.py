# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""ECS Fargate, 내부 ALB, ECR, EFS로 구성된 PingFederate IdP 스택입니다."""

from aws_cdk import CfnOutput, CustomResource, Duration, RemovalPolicy, Stack
from aws_cdk import aws_certificatemanager as acm
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecr as ecr
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_efs as efs
from aws_cdk import aws_elasticloadbalancingv2 as elbv2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_route53 as route53
from aws_cdk import aws_route53_targets as targets
from aws_cdk import aws_secretsmanager as secretsmanager
from cdk_ecr_deployment import DockerImageName, ECRDeployment
from constructs import Construct

from config import CdkConfig

PING_FEDERATE_ENGINE_PORT = 9031
PING_FEDERATE_ADMIN_PORT = 9999


class PingFederateStack(Stack):
    """내부 ALB 뒤의 ECS Fargate에 자체 호스팅 PingFederate IdP를 배포합니다."""

    def __init__(self, scope: Construct, id: str, vpc: ec2.IVpc, config: CdkConfig, **kwargs):
        """PingFederate 스택을 초기화합니다."""
        super().__init__(scope, id, **kwargs)

        self.vpc = vpc
        self.ping_domain = config.ping_domain

        # --- 퍼블릭 ACM 인증서(사용자 제공) ---
        # AgentCore Identity가 VPC Lattice를 통해 프라이빗 IdP에 연결하려면
        # 공개적으로 신뢰할 수 있는 TLS 인증서가 필요하며, ALB는 내부용으로 유지됨
        certificate = acm.Certificate.from_certificate_arn(self, "AlbCertificate", config.certificate_arn)

        # --- Secrets Manager ---
        ping_secret = secretsmanager.Secret(
            self,
            "PingFederateSecret",
            secret_name=f"pingfederate-devops-{config.suffix}",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                generate_string_key="adminPassword",
                exclude_punctuation=True,
                password_length=20,
                secret_string_template=(
                    f'{{"username":"{config.ping_federate_config.devops_user}",'
                    f'"key":"{config.ping_federate_config.devops_key}",'
                    f'"adminUsername":"Administrator"}}'
                ),
            ),
        )

        # --- EFS ---
        file_system = efs.FileSystem(
            self,
            "FileSystem",
            vpc=self.vpc,
            removal_policy=RemovalPolicy.DESTROY,
            encrypted=True,
        )

        access_point = efs.AccessPoint(
            self,
            "AccessPoint",
            file_system=file_system,
            path="/pingfederate",
            posix_user=efs.PosixUser(uid="9031", gid="9999"),
            create_acl=efs.Acl(owner_uid="9031", owner_gid="9999", permissions="755"),
        )

        # --- ECR ---
        ecr_repo = ecr.Repository(
            self,
            "EcrRepo",
            repository_name=f"pingfederate-{config.suffix}",
            removal_policy=RemovalPolicy.DESTROY,
            empty_on_delete=True,
        )

        ECRDeployment(
            self,
            "ImageDeployment",
            src=DockerImageName("pingidentity/pingfederate:latest"),
            dest=DockerImageName(f"{ecr_repo.repository_uri}:latest"),
        )

        # --- ECS 클러스터 + 태스크 정의 ---
        cluster = ecs.Cluster(
            self,
            "Cluster",
            vpc=self.vpc,
            container_insights_v2=ecs.ContainerInsights.ENABLED,
        )

        execution_role = iam.Role(
            self,
            "ExecutionRole",
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("ecs.amazonaws.com"),
                iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            ),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEC2ContainerRegistryReadOnly"),
            ],
        )

        task_def = ecs.FargateTaskDefinition(
            self,
            "TaskDef",
            cpu=2048,
            memory_limit_mib=4096,
            execution_role=execution_role,
        )

        log_group = logs.LogGroup(
            self,
            "LogGroup",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY,
        )

        environment = {
            "PING_IDENTITY_ACCEPT_EULA": "YES",
            "CREATE_INITIAL_ADMIN_USER": "true",
            "PF_ADMIN_PUBLIC_HOSTNAME": self.ping_domain,
            "PF_ADMIN_PUBLIC_BASEURL": f"https://{self.ping_domain}:{PING_FEDERATE_ADMIN_PORT}",
            "PF_ENGINE_PUBLIC_HOSTNAME": self.ping_domain,
            "PF_ENGINE_BASE_URL": f"https://{self.ping_domain}",
        }

        secrets = {
            "PING_IDENTITY_DEVOPS_USER": ecs.Secret.from_secrets_manager(ping_secret, "username"),
            "PING_IDENTITY_DEVOPS_KEY": ecs.Secret.from_secrets_manager(ping_secret, "key"),
            "PING_IDENTITY_PASSWORD": ecs.Secret.from_secrets_manager(ping_secret, "adminPassword"),
        }

        container = task_def.add_container(
            "pingfederate",
            image=ecs.ContainerImage.from_registry(f"{ecr_repo.repository_uri}:latest"),
            environment=environment,
            secrets=secrets,
            logging=ecs.LogDrivers.aws_logs(stream_prefix="pingfederate", log_group=log_group),
        )
        container.add_port_mappings(
            ecs.PortMapping(container_port=PING_FEDERATE_ENGINE_PORT),
            ecs.PortMapping(container_port=PING_FEDERATE_ADMIN_PORT),
        )

        # EFS 볼륨
        task_def.add_volume(
            name="pingfederate-data",
            efs_volume_configuration=ecs.EfsVolumeConfiguration(
                file_system_id=file_system.file_system_id,
                transit_encryption="ENABLED",
                authorization_config=ecs.AuthorizationConfig(
                    access_point_id=access_point.access_point_id,
                    iam="ENABLED",
                ),
            ),
        )
        container.add_mount_points(
            ecs.MountPoint(
                source_volume="pingfederate-data",
                container_path="/opt/out/instance",
                read_only=False,
            )
        )

        file_system.grant_read_write(task_def.task_role)
        ping_secret.grant_read(execution_role)

        # --- ECS 서비스 ---
        service = ecs.FargateService(
            self,
            "Service",
            cluster=cluster,
            task_definition=task_def,
            circuit_breaker=ecs.DeploymentCircuitBreaker(rollback=True),
            desired_count=1,
            health_check_grace_period=Duration.seconds(120),
            platform_version=ecs.FargatePlatformVersion.LATEST,
        )

        file_system.connections.allow_default_port_from(service)

        # --- 내부 ALB ---
        alb_sg = ec2.SecurityGroup(
            self,
            "AlbSg",
            vpc=self.vpc,
            description="Internal ALB security group",
            allow_all_outbound=True,
        )
        alb_sg.add_ingress_rule(ec2.Peer.ipv4(self.vpc.vpc_cidr_block), ec2.Port.tcp(443), "HTTPS from VPC")
        alb_sg.add_ingress_rule(
            ec2.Peer.ipv4(self.vpc.vpc_cidr_block),
            ec2.Port.tcp(PING_FEDERATE_ADMIN_PORT),
            "HTTPS admin from VPC",
        )

        self.alb = elbv2.ApplicationLoadBalancer(
            self,
            "InternalAlb",
            vpc=self.vpc,
            internet_facing=False,
            security_group=alb_sg,
            drop_invalid_header_fields=True,
        )

        self.alb_listener = self.alb.add_listener(
            "HttpsListener",
            port=443,
            protocol=elbv2.ApplicationProtocol.HTTPS,
            certificates=[certificate],
            ssl_policy=elbv2.SslPolicy.TLS12,
        )

        self.alb_listener.add_targets(
            "EngineTarget",
            targets=[
                service.load_balancer_target(
                    container_name="pingfederate",
                    container_port=PING_FEDERATE_ENGINE_PORT,
                )
            ],
            health_check=elbv2.HealthCheck(
                healthy_threshold_count=3,
                path="/pf/heartbeat.ping",
            ),
            slow_start=Duration.seconds(60),
            port=PING_FEDERATE_ENGINE_PORT,
            protocol=elbv2.ApplicationProtocol.HTTPS,
        )

        # Lambda 사용자 지정 리소스에서 사용하는 Admin API 리스너(포트 9999)
        admin_listener = self.alb.add_listener(
            "AdminListener",
            port=PING_FEDERATE_ADMIN_PORT,
            protocol=elbv2.ApplicationProtocol.HTTPS,
            certificates=[certificate],
            ssl_policy=elbv2.SslPolicy.TLS12,
        )
        admin_listener.add_targets(
            "AdminTarget",
            targets=[
                service.load_balancer_target(
                    container_name="pingfederate",
                    container_port=PING_FEDERATE_ADMIN_PORT,
                )
            ],
            health_check=elbv2.HealthCheck(
                healthy_threshold_count=3,
                path="/pf/heartbeat.ping",
                port=str(PING_FEDERATE_ADMIN_PORT),
            ),
            port=PING_FEDERATE_ADMIN_PORT,
            protocol=elbv2.ApplicationProtocol.HTTPS,
        )

        # --- 프라이빗 호스팅 영역 ---
        # VPC Lattice Resource Gateway는 VPC 내부에서 검색 URL 도메인을 확인함
        # 프라이빗 호스팅 영역은 인증서 도메인을 내부 ALB에 매핑하여 AgentCore Identity가
        # 퍼블릭 도메인 이름으로 PingFederate에 접근할 수 있게 함
        private_zone = route53.PrivateHostedZone(
            self,
            "PrivateZone",
            zone_name=self.ping_domain,
            vpc=self.vpc,
        )
        route53.ARecord(
            self,
            "AlbAliasRecord",
            zone=private_zone,
            target=route53.RecordTarget.from_alias(targets.LoadBalancerTarget(self.alb)),
        )

        # --- Lambda 사용자 지정 리소스: PingFederate 구성 ---
        configure_fn = lambda_.Function(
            self,
            "ConfigurePingFedFn",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.handler",
            code=lambda_.Code.from_asset("lambda/configure_pingfed"),
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            timeout=Duration.minutes(10),
            memory_size=256,
            log_retention=logs.RetentionDays.ONE_MONTH,
        )

        # Lambda가 내부 ALB에 접근하도록 허용(엔진 및 관리 포트의 HTTPS)
        configure_fn.connections.allow_to(alb_sg, ec2.Port.tcp(443), "HTTPS to ALB engine")
        configure_fn.connections.allow_to(alb_sg, ec2.Port.tcp(PING_FEDERATE_ADMIN_PORT), "HTTPS to ALB admin")

        # Lambda가 Secrets Manager에서 관리자 암호를 읽도록 허용
        ping_secret.grant_read(configure_fn)

        admin_url = f"https://{self.alb.load_balancer_dns_name}:{PING_FEDERATE_ADMIN_PORT}"
        engine_url = f"https://{self.ping_domain}"

        configure_resource = CustomResource(
            self,
            "ConfigurePingFed",
            service_token=configure_fn.function_arn,
            properties={
                "AdminUrl": admin_url,
                "AdminUser": "Administrator",
                "SecretId": ping_secret.secret_name,
                "BaseUrl": engine_url,
            },
        )
        configure_resource.node.add_dependency(service)

        # --- 출력 ---
        self.discovery_url = f"https://{self.ping_domain}/.well-known/openid-configuration"

        CfnOutput(self, "SecretName", value=ping_secret.secret_name)
        CfnOutput(self, "AlbDnsName", value=self.alb.load_balancer_dns_name)
        CfnOutput(self, "AlbArn", value=self.alb.load_balancer_arn)
        CfnOutput(
            self,
            "DiscoveryUrl",
            value=self.discovery_url,
            description="PingFederate OIDC discovery URL (uses public domain, reachable via VPC Lattice)",
        )
        CfnOutput(self, "PingDomain", value=self.ping_domain)

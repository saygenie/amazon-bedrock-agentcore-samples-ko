# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""세션 스토리지용 S3 버킷 construct."""

from aws_cdk import Duration
from aws_cdk import aws_kms as kms
from aws_cdk import aws_s3 as s3
from constructs import Construct


class S3Bucket(Construct):
    """액세스 로그 및 세션 스토리지용 S3 버킷."""

    def __init__(
        self,
        scope: Construct,
        id: str,
        suffix: str,
        account_id: str,
        session_expiration_in_days: int,
        kms_key: kms.Key,
    ):
        """S3 버킷을 초기화한다."""
        super().__init__(scope, id)

        self.access_logs_bucket = s3.Bucket(
            self,
            "AccessLogsBucket",
            bucket_name=f"access-logs-{account_id}-{suffix}",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="AccessLogsLifecycle",
                    enabled=True,
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.GLACIER_INSTANT_RETRIEVAL,
                            transition_after=Duration.days(90),
                        ),
                    ],
                    expiration=Duration.days(365 * 5),
                )
            ],
        )
        cfn_access_logs_bucket = self.access_logs_bucket.node.default_child
        cfn_access_logs_bucket.add_metadata(
            "checkov",
            {
                "skip": [
                    {
                        "id": "CKV_AWS_18",
                        "comment": "Access logs bucket does not need its own access logging",
                    },
                    {
                        "id": "CKV_AWS_21",
                        "comment": "Versioning not needed for access logs bucket",
                    },
                ]
            },
        )

        self.sessions_bucket = s3.Bucket(
            self,
            "SessionsBucket",
            bucket_name=f"sessions-{account_id}-{suffix}",
            versioned=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            bucket_key_enabled=True,
            encryption_key=kms_key,
            server_access_logs_bucket=self.access_logs_bucket,
            server_access_logs_prefix="sessions-bucket/",
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="AgentSessionsLifecycle",
                    enabled=True,
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.GLACIER_INSTANT_RETRIEVAL,
                            transition_after=Duration.days(30),
                        ),
                    ],
                    expiration=Duration.days(session_expiration_in_days),
                )
            ],
        )

# 관리자 승인 워크플로 예제의 IAM 권한

다음 권한을 가진 IAM 사용자 또는 역할을 생성합니다.

> **이 정책을 사용하기 전에** 모든 `YOUR_ACCOUNT_ID`를 12자리 AWS 계정 ID로 바꾸세요.
> 계정 ID를 확인하려면 다음 명령을 실행합니다.
> ```bash
> aws sts get-caller-identity --query Account --output text
> ```
> 정책을 연결하기 전에 아래 JSON에서 `YOUR_ACCOUNT_ID`를 찾아 모두 바꾸세요.

## AWS Agent Registry 액세스 정책(관리자)

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AllowCreatingAndListingRegistries",
            "Effect": "Allow",
            "Action": [
                "bedrock-agentcore:CreateRegistry",
                "bedrock-agentcore:ListRegistries"
            ],
            "Resource": ["arn:aws:bedrock-agentcore:*:YOUR_ACCOUNT_ID:*"]
        },
        {
            "Sid": "AllowGetUpdateDeleteRegistry",
            "Effect": "Allow",
            "Action": [
                "bedrock-agentcore:GetRegistry",
                "bedrock-agentcore:UpdateRegistry",
                "bedrock-agentcore:DeleteRegistry"
            ],
            "Resource": ["arn:aws:bedrock-agentcore:*:YOUR_ACCOUNT_ID:registry/*"]
        },
        {
            "Sid": "AllowCreatingAndListingRegistryRecords",
            "Effect": "Allow",
            "Action": [
                "bedrock-agentcore:CreateRegistryRecord",
                "bedrock-agentcore:ListRegistryRecords"
            ],
            "Resource": ["arn:aws:bedrock-agentcore:*:YOUR_ACCOUNT_ID:registry/*"]
        },
        {
            "Sid": "AllowRecordLevelOperations",
            "Effect": "Allow",
            "Action": [
                "bedrock-agentcore:GetRegistryRecord",
                "bedrock-agentcore:UpdateRegistryRecord",
                "bedrock-agentcore:DeleteRegistryRecord",
                "bedrock-agentcore:SubmitRegistryRecordForApproval"
            ],
            "Resource": ["arn:aws:bedrock-agentcore:*:YOUR_ACCOUNT_ID:registry/*/record/*"]
        },
        {
            "Sid": "AllowApproveRejectDeprecateRecords",
            "Effect": "Allow",
            "Action": ["bedrock-agentcore:UpdateRegistryRecordStatus"],
            "Resource": ["arn:aws:bedrock-agentcore:*:YOUR_ACCOUNT_ID:registry/*/record/*"]
        },
        {
            "Sid": "AdditionalPermissionForRegistryManagedWorkloadIdentity",
            "Effect": "Allow",
            "Action": ["bedrock-agentcore:*WorkloadIdentity"],
            "Resource": ["arn:aws:bedrock-agentcore:*:YOUR_ACCOUNT_ID:workload-identity-directory/default/workload-identity/*"]
        }
    ]
}
```

## AWS Agent Registry 액세스 정책(게시자)

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AllowListingAllRegistries",
            "Effect": "Allow",
            "Action": ["bedrock-agentcore:ListRegistries"],
            "Resource": ["arn:aws:bedrock-agentcore:*:YOUR_ACCOUNT_ID:*"]
        },
        {
            "Sid": "AllowGetRegistry",
            "Effect": "Allow",
            "Action": ["bedrock-agentcore:GetRegistry"],
            "Resource": ["arn:aws:bedrock-agentcore:*:YOUR_ACCOUNT_ID:registry/*"]
        },
        {
            "Sid": "AllowCreatingAndListingRegistryRecords",
            "Effect": "Allow",
            "Action": [
                "bedrock-agentcore:CreateRegistryRecord",
                "bedrock-agentcore:ListRegistryRecords"
            ],
            "Resource": ["arn:aws:bedrock-agentcore:*:YOUR_ACCOUNT_ID:registry/*"]
        },
        {
            "Sid": "AllowRecordLevelOperations",
            "Effect": "Allow",
            "Action": [
                "bedrock-agentcore:GetRegistryRecord",
                "bedrock-agentcore:UpdateRegistryRecord",
                "bedrock-agentcore:DeleteRegistryRecord",
                "bedrock-agentcore:SubmitRegistryRecordForApproval"
            ],
            "Resource": ["arn:aws:bedrock-agentcore:*:YOUR_ACCOUNT_ID:registry/*/record/*"]
        }
    ]
}
```

## DynamoDB, AWS Lambda 등 필수 CI/CD 스택 배포에 필요한 권한

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "STSCallerIdentity",
            "Effect": "Allow",
            "Action": ["sts:GetCallerIdentity"],
            "Resource": "*"
        },
        {
            "Sid": "CloudFormationValidate",
            "Effect": "Allow",
            "Action": ["cloudformation:ValidateTemplate"],
            "Resource": "*"
        },
        {
            "Sid": "CloudFormationStackManagement",
            "Effect": "Allow",
            "Action": [
                "cloudformation:CreateStack",
                "cloudformation:UpdateStack",
                "cloudformation:DeleteStack",
                "cloudformation:DescribeStacks",
                "cloudformation:DescribeStackEvents",
                "cloudformation:DescribeStackResources",
                "cloudformation:GetTemplate",
                "cloudformation:ListStackResources",
                "cloudformation:CreateChangeSet",
                "cloudformation:DescribeChangeSet",
                "cloudformation:ExecuteChangeSet",
                "cloudformation:DeleteChangeSet"
            ],
            "Resource": "arn:aws:cloudformation:*:YOUR_ACCOUNT_ID:stack/*/*"
        },
        {
            "Sid": "S3StagingBucketManagement",
            "Effect": "Allow",
            "Action": [
                "s3:CreateBucket",
                "s3:DeleteBucket",
                "s3:HeadBucket",
                "s3:PutBucketPublicAccessBlock",
                "s3:GetBucketPublicAccessBlock",
                "s3:ListBucket",
                "s3:DeleteObject",
                "s3:PutObject",
                "s3:GetObject"
            ],
            "Resource": [
                "arn:aws:s3:::*",
                "arn:aws:s3:::*/*"
            ]
        },
        {
            "Sid": "LambdaFunctionManagement",
            "Effect": "Allow",
            "Action": [
                "lambda:CreateFunction",
                "lambda:UpdateFunctionCode",
                "lambda:UpdateFunctionConfiguration",
                "lambda:DeleteFunction",
                "lambda:GetFunction",
                "lambda:GetFunctionConfiguration",
                "lambda:AddPermission",
                "lambda:RemovePermission"
            ],
            "Resource": "arn:aws:lambda:*:YOUR_ACCOUNT_ID:function:*"
        },
        {
            "Sid": "LambdaLayerManagement",
            "Effect": "Allow",
            "Action": [
                "lambda:PublishLayerVersion",
                "lambda:DeleteLayerVersion",
                "lambda:GetLayerVersion",
                "lambda:ListLayerVersions"
            ],
            "Resource": "arn:aws:lambda:*:YOUR_ACCOUNT_ID:layer:*"
        },
        {
            "Sid": "IAMRoleManagement",
            "Effect": "Allow",
            "Action": [
                "iam:CreateRole",
                "iam:DeleteRole",
                "iam:GetRole",
                "iam:PassRole",
                "iam:AttachRolePolicy",
                "iam:DetachRolePolicy",
                "iam:PutRolePolicy",
                "iam:DeleteRolePolicy",
                "iam:GetRolePolicy",
                "iam:ListRolePolicies",
                "iam:ListAttachedRolePolicies"
            ],
            "Resource": "arn:aws:iam::YOUR_ACCOUNT_ID:role/*"
        },
        {
            "Sid": "KMSCreateKey",
            "Effect": "Allow",
            "Action": ["kms:CreateKey"],
            "Resource": "*"
        },
        {
            "Sid": "KMSManageTaggedKeys",
            "Effect": "Allow",
            "Action": [
                "kms:DescribeKey",
                "kms:EnableKeyRotation",
                "kms:GetKeyPolicy",
                "kms:PutKeyPolicy",
                "kms:ScheduleKeyDeletion",
                "kms:CancelKeyDeletion",
                "kms:TagResource",
                "kms:UntagResource"
            ],
            "Resource": "*"
        },
        {
            "Sid": "DynamoDBTableManagement",
            "Effect": "Allow",
            "Action": [
                "dynamodb:CreateTable",
                "dynamodb:DeleteTable",
                "dynamodb:DescribeTable",
                "dynamodb:UpdateTable",
                "dynamodb:DescribeContinuousBackups",
                "dynamodb:DescribeTimeToLive"
            ],
            "Resource": "arn:aws:dynamodb:*:YOUR_ACCOUNT_ID:table/*"
        },
        {
            "Sid": "EventBridgeManagement",
            "Effect": "Allow",
            "Action": [
                "events:PutRule",
                "events:DeleteRule",
                "events:DescribeRule",
                "events:PutTargets",
                "events:RemoveTargets",
                "events:ListTargetsByRule"
            ],
            "Resource": "arn:aws:events:*:YOUR_ACCOUNT_ID:rule/*"
        }
    ]
}
```


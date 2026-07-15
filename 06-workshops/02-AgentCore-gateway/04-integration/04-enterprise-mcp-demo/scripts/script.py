import boto3

output = """
EnterpriseMcpInfraStack.ApiGatewayDefaultUrl =
EnterpriseMcpInfraStack.ApiGatewayEndpoint =
EnterpriseMcpInfraStack.ApiGatewayId =
EnterpriseMcpInfraStack.CognitoDomain =
EnterpriseMcpInfraStack.CognitoDomainUrl =
EnterpriseMcpInfraStack.DeploymentTypeOutput =
EnterpriseMcpInfraStack.DiscoveryUrl =
EnterpriseMcpInfraStack.EndpointUrl =
EnterpriseMcpInfraStack.Gateway =
EnterpriseMcpInfraStack.PreTokenGenerationLambdaArn =
EnterpriseMcpInfraStack.PreTokenGenerationLambdaName = E
EnterpriseMcpInfraStack.ProxyLambdaName =
EnterpriseMcpInfraStack.UserPoolArn =
EnterpriseMcpInfraStack.UserPoolId =
EnterpriseMcpInfraStack.VSCodeClientId =
EnterpriseMcpInfraStack.VSCodeMcpConfig = {
  "servers": {
    "enterprise-mcp-server": {
      "type": "http",
      "url": ""
    }
  }
}
"""

config = {}
for el in output.split("\n"):
    if "=" in el:
        key, value = el.split("=", 1)
        config[key.strip().replace("EnterpriseMcpInfraStack.", "")] = value.strip()


# 생성할 사용자 - Cognito 사용자 이름으로 이메일 사용
users = [
    {
        "COGNITO_USERNAME": "vscode-admin@example.com",
        "COGNITO_PASSWORD": "TempPassword123!",  # pragma: allowlist secret
    },
    {
        "COGNITO_USERNAME": "vscode-user@example.com",
        "COGNITO_PASSWORD": "TempPassword1234!",  # pragma: allowlist secret
    },
]

cognito = boto3.client("cognito-idp")
user_pool_id = config["UserPoolId"]

        # 이메일을 사용자 이름으로 사용하여 사용자 생성
for user in users:
    COGNITO_USERNAME = user["COGNITO_USERNAME"]
    COGNITO_PASSWORD = user["COGNITO_PASSWORD"]
    try:
                # 이메일을 사용자 이름으로 사용하여 사용자 생성
        cognito.admin_create_user(
            UserPoolId=user_pool_id,
            Username=COGNITO_USERNAME,
            TemporaryPassword=COGNITO_PASSWORD,
            MessageAction="SUPPRESS",
            UserAttributes=[
                {"Name": "email", "Value": f"{COGNITO_USERNAME}"},
                {"Name": "email_verified", "Value": "true"},
            ],
        )
        cognito.admin_set_user_password(
            UserPoolId=user_pool_id,
            Username=COGNITO_USERNAME,
            Password=COGNITO_PASSWORD,
            Permanent=True,
        )
        print(f"✓ User created: {user['COGNITO_USERNAME']}")
    except cognito.exceptions.UsernameExistsException:
        print(f"✓ User exists: {user['COGNITO_USERNAME']}")

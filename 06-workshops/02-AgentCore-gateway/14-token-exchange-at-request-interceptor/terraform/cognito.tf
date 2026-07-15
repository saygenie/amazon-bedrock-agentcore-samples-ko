# -----------------------------------------------------------------------------
# Cognito User Pool
# -----------------------------------------------------------------------------
resource "aws_cognito_user_pool" "this" {
  name = "${var.name_prefix}-pool-${local.suffix}"

  password_policy {
    minimum_length    = 8
    require_uppercase = false
    require_lowercase = false
    require_numbers   = false
    require_symbols   = false
  }
}

# Essentials tier로 업그레이드(V3_0 Pre Token Generation에 필요).
# 그런 다음 Pre Token Generation Lambda 트리거를 연결합니다.
# aws_cognito_user_pool 리소스는 UserPoolTier를 기본 지원하지 않고
# V3_0 트리거에는 Essentials tier가 필요하므로 두 작업 모두 CLI로 수행합니다.
resource "null_resource" "configure_user_pool" {
  depends_on = [
    aws_cognito_user_pool.this,
    aws_lambda_function.pre_token_generation,
    aws_lambda_permission.cognito_pre_token,
  ]

  triggers = {
    user_pool_id = aws_cognito_user_pool.this.id
    lambda_arn   = aws_lambda_function.pre_token_generation.arn
  }

  provisioner "local-exec" {
    command = <<-EOT
      aws cognito-idp update-user-pool \
        --user-pool-id ${aws_cognito_user_pool.this.id} \
        --user-pool-tier ESSENTIALS \
        --region ${local.region}

      sleep 5

      aws cognito-idp update-user-pool \
        --user-pool-id ${aws_cognito_user_pool.this.id} \
        --lambda-config '{"PreTokenGeneration":"${aws_lambda_function.pre_token_generation.arn}","PreTokenGenerationConfig":{"LambdaVersion":"V3_0","LambdaArn":"${aws_lambda_function.pre_token_generation.arn}"}}' \
        --region ${local.region}
    EOT
  }
}

# -----------------------------------------------------------------------------
# Cognito User Pool Domain
# -----------------------------------------------------------------------------
resource "aws_cognito_user_pool_domain" "this" {
  domain       = local.cognito_domain
  user_pool_id = aws_cognito_user_pool.this.id
}

# -----------------------------------------------------------------------------
# Cognito Resource Server
# -----------------------------------------------------------------------------
resource "aws_cognito_resource_server" "this" {
  identifier   = local.resource_server_id
  name         = "AgentCore API ${local.suffix}"
  user_pool_id = aws_cognito_user_pool.this.id

  scope {
    scope_name        = "read"
    scope_description = "Read access to AgentCore Gateway"
  }

  scope {
    scope_name        = "write"
    scope_description = "Write access to AgentCore Gateway"
  }
}

# -----------------------------------------------------------------------------
# Cognito App Client - Gateway(AgentCore Gateway 인바운드 인증)
# -----------------------------------------------------------------------------
resource "aws_cognito_user_pool_client" "gateway" {
  name         = "${var.name_prefix}-gateway-client-${local.suffix}"
  user_pool_id = aws_cognito_user_pool.this.id

  generate_secret                      = true
  allowed_oauth_flows                  = ["client_credentials"]
  allowed_oauth_flows_user_pool_client = true
  supported_identity_providers         = ["COGNITO"]

  allowed_oauth_scopes = [
    "${local.resource_server_id}/read",
    "${local.resource_server_id}/write",
  ]

  depends_on = [aws_cognito_resource_server.this]
}

# -----------------------------------------------------------------------------
# Cognito App Client - Downstream(인터셉터가 API Gateway 인증에 사용)
# -----------------------------------------------------------------------------
resource "aws_cognito_user_pool_client" "downstream" {
  name         = "${var.name_prefix}-downstream-client-${local.suffix}"
  user_pool_id = aws_cognito_user_pool.this.id

  generate_secret                      = true
  allowed_oauth_flows                  = ["client_credentials"]
  allowed_oauth_flows_user_pool_client = true
  supported_identity_providers         = ["COGNITO"]

  allowed_oauth_scopes = [
    "${local.resource_server_id}/read",
    "${local.resource_server_id}/write",
  ]

  depends_on = [aws_cognito_resource_server.this]
}

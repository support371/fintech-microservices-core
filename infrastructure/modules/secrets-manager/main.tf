# =============================================================================
# AWS Secrets Manager Module
# =============================================================================

resource "aws_secretsmanager_secret" "striga_api" {
  name                    = "${var.project_name}/${var.environment}/striga-api"
  description             = "Striga API credentials"
  recovery_window_in_days = 30
  kms_key_id              = aws_kms_key.secrets.arn

  tags = {
    Name       = "${var.project_name}-${var.environment}-striga-api"
    Compliance = "pci-dss"
  }
}

resource "aws_secretsmanager_secret" "database" {
  name                    = "${var.project_name}/${var.environment}/database"
  description             = "Database credentials"
  recovery_window_in_days = 30
  kms_key_id              = aws_kms_key.secrets.arn

  tags = {
    Name       = "${var.project_name}-${var.environment}-database"
    Compliance = "pci-dss"
  }
}

resource "aws_secretsmanager_secret" "webhook" {
  name                    = "${var.project_name}/${var.environment}/webhook-secrets"
  description             = "Webhook signing secrets"
  recovery_window_in_days = 30
  kms_key_id              = aws_kms_key.secrets.arn

  tags = {
    Name       = "${var.project_name}-${var.environment}-webhook-secrets"
    Compliance = "pci-dss"
  }
}

resource "aws_secretsmanager_secret" "jwt" {
  name                    = "${var.project_name}/${var.environment}/jwt-signing-key"
  description             = "JWT signing key for service authentication"
  recovery_window_in_days = 30
  kms_key_id              = aws_kms_key.secrets.arn

  tags = {
    Name       = "${var.project_name}-${var.environment}-jwt-signing-key"
    Compliance = "pci-dss"
  }
}

# Automatic rotation for database credentials
resource "aws_secretsmanager_secret_rotation" "database" {
  secret_id           = aws_secretsmanager_secret.database.id
  rotation_lambda_arn = aws_lambda_function.secret_rotation.arn

  rotation_rules {
    automatically_after_days = 90
  }
}

# KMS key for encrypting all secrets
resource "aws_kms_key" "secrets" {
  description             = "KMS key for Secrets Manager encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {
    Name = "${var.project_name}-${var.environment}-secrets-kms"
  }
}

resource "aws_kms_alias" "secrets" {
  name          = "alias/${var.project_name}-${var.environment}-secrets"
  target_key_id = aws_kms_key.secrets.key_id
}

# Lambda for secret rotation
resource "aws_lambda_function" "secret_rotation" {
  function_name = "${var.project_name}-${var.environment}-secret-rotation"
  role          = aws_iam_role.rotation_lambda.arn
  handler       = "index.handler"
  runtime       = "python3.11"
  timeout       = 30

  filename = "${path.module}/rotation_lambda.zip"

  environment {
    variables = {
      SECRETS_MANAGER_ENDPOINT = "https://secretsmanager.${data.aws_region.current.name}.amazonaws.com"
    }
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-secret-rotation"
  }
}

data "aws_region" "current" {}

resource "aws_iam_role" "rotation_lambda" {
  name = "${var.project_name}-${var.environment}-secret-rotation-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "rotation_lambda" {
  name = "${var.project_name}-${var.environment}-secret-rotation-policy"
  role = aws_iam_role.rotation_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "secretsmanager:DescribeSecret",
          "secretsmanager:GetSecretValue",
          "secretsmanager:PutSecretValue",
          "secretsmanager:UpdateSecretVersionStage"
        ]
        Effect   = "Allow"
        Resource = "*"
      },
      {
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Effect   = "Allow"
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

resource "aws_lambda_permission" "secrets_manager" {
  statement_id  = "AllowSecretsManagerInvocation"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.secret_rotation.function_name
  principal     = "secretsmanager.amazonaws.com"
}

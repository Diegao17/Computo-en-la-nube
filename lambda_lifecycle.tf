########################################
# IAM ROLE para Lambda data_lifecycle
########################################

resource "aws_iam_role" "lambda_data_lifecycle_role" {
  name = "${var.project_name}-lambda-data-lifecycle-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Name        = "${var.project_name}-lambda-data-lifecycle-role"
    Environment = var.environment
  }
}

########################################
# POLÍTICA de permisos para lifecycle
########################################

resource "aws_iam_role_policy" "lambda_data_lifecycle_policy" {
  name = "${var.project_name}-lambda-data-lifecycle-policy"
  role = aws_iam_role.lambda_data_lifecycle_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # Permisos para DynamoDB (lab_results + access_audit)
      {
        Effect = "Allow"
        Action = [
          "dynamodb:Scan",
          "dynamodb:UpdateItem",
          "dynamodb:PutItem",
          "dynamodb:GetItem"
        ]
        Resource = [
          aws_dynamodb_table.lab_results.arn,
          aws_dynamodb_table.access_audit.arn
        ]
      },
      # Permisos para logs de CloudWatch
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

########################################
# LAMBDA data_lifecycle
########################################

resource "aws_lambda_function" "data_lifecycle" {
  function_name = "${var.project_name}-data-lifecycle"
  description   = "Lambda para manejo de ciclo de vida de datos (HIPAA/GDPR) - Scenario F"

  # IMPORTANTE: este zip lo generas tú con:
  #   cd lambda/data_lifecycle
  #   zip data_lifecycle.zip app.py
  filename         = "${path.module}/lambda/data_lifecycle/data_lifecycle.zip"
  source_code_hash = filebase64sha256("${path.module}/lambda/data_lifecycle/data_lifecycle.zip")

  handler = "app.lambda_handler"
  runtime = "python3.12"

  role         = aws_iam_role.lambda_data_lifecycle_role.arn
  timeout      = 300
  memory_size  = 256
  architectures = ["x86_64"]

  environment {
    variables = {
      REGION_NAME        = var.region
      LAB_RESULTS_TABLE  = aws_dynamodb_table.lab_results.name
      ACCESS_AUDIT_TABLE = aws_dynamodb_table.access_audit.name
    }
  }

  tags = {
    Name        = "${var.project_name}-lambda-data-lifecycle"
    Environment = var.environment
  }
}

########################################
# EVENTBRIDGE REGLA: ejecútalo diario
########################################

resource "aws_cloudwatch_event_rule" "data_lifecycle_daily" {
  name                = "${var.project_name}-data-lifecycle-daily"
  description         = "Ejecuta Lambda de data lifecycle 1 vez al día"
  schedule_expression = "rate(1 day)"

  tags = {
    Environment = var.environment
  }
}

resource "aws_cloudwatch_event_target" "data_lifecycle_target" {
  rule      = aws_cloudwatch_event_rule.data_lifecycle_daily.name
  target_id = "lambda-data-lifecycle"
  arn       = aws_lambda_function.data_lifecycle.arn
}

########################################
# PERMISO para que EventBridge invoque la Lambda
########################################

resource "aws_lambda_permission" "allow_eventbridge_data_lifecycle" {
  statement_id  = "AllowExecutionFromEventBridgeDataLifecycle"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.data_lifecycle.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.data_lifecycle_daily.arn
}

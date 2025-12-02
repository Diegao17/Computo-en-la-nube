# Rol para Lambda de notificación
resource "aws_iam_role" "lambda_notify_role" {
  name = "${var.project_name}-lambda-notify-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect    = "Allow",
      Principal = { Service = "lambda.amazonaws.com" },
      Action    = "sts:AssumeRole"
    }]
  })
}

# Permisos básicos de logs
resource "aws_iam_role_policy_attachment" "lambda_notify_basic" {
  role       = aws_iam_role.lambda_notify_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Permisos extra: DynamoDB + SNS
resource "aws_iam_role_policy" "lambda_notify_policy" {
  name = "${var.project_name}-lambda-notify-policy"
  role = aws_iam_role.lambda_notify_role.id

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      # DynamoDB: leer pacientes y registrar auditoría
      {
        Effect = "Allow",
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem"
        ],
        Resource = [
          aws_dynamodb_table.patients.arn,
          aws_dynamodb_table.access_audit.arn
        ]
      },

      # SNS: enviar notificación
      {
        Effect = "Allow",
        Action = [
          "sns:Publish"
        ],
        Resource = aws_sns_topic.lab_results_ready.arn
      },

      # SQS: recibir mensajes desde notify_queue
      {
        Effect = "Allow",
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ],
        Resource = aws_sqs_queue.notify_queue.arn
      }
    ]
  })
}

# Función Lambda de notificación
resource "aws_lambda_function" "notify" {
  function_name = "${var.project_name}-notify"
  role          = aws_iam_role.lambda_notify_role.arn
  runtime       = "python3.11"
  handler       = "app.lambda_handler"

  filename         = "${path.module}/../lambda/notify.zip"
  source_code_hash = filebase64sha256("${path.module}/../lambda/notify.zip")

  environment {
    variables = {
      REGION_NAME        = var.region
      PATIENTS_TABLE     = aws_dynamodb_table.patients.name
      ACCESS_AUDIT_TABLE = aws_dynamodb_table.access_audit.name
      NOTIFY_TOPIC_ARN   = aws_sns_topic.lab_results_ready.arn
    }
  }
}

# Conectar la cola notify_queue con la Lambda
resource "aws_lambda_event_source_mapping" "notify_sqs_mapping" {
  event_source_arn = aws_sqs_queue.notify_queue.arn
  function_name    = aws_lambda_function.notify.arn
  batch_size       = 5
  enabled          = true
}


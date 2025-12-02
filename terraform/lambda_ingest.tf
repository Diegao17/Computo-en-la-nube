resource "aws_iam_role" "lambda_ingest_role" {
  name = "${var.project_name}-lambda-ingest-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect    = "Allow",
      Principal = { Service = "lambda.amazonaws.com" },
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_ingest_basic" {
  role       = aws_iam_role.lambda_ingest_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "lambda_ingest_policy" {
  name = "${var.project_name}-lambda-ingest-policy"
  role = aws_iam_role.lambda_ingest_role.id # <- si tu rol se llama diferente, ajusta esta línea

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # S3: guardar raw en el bucket
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject"
        ]
        Resource = [
          "arn:aws:s3:::${var.raw_bucket_name}/*"
        ]
      },

      # SQS: enviar mensaje a la cola de resultados
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage"
        ]
        Resource = [
          aws_sqs_queue.lab_results_queue.arn
        ]
      },

      # DynamoDB: leer estado de resultados (para /status)
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:Query"
        ]
        Resource = [
          aws_dynamodb_table.lab_results.arn
        ]
      },

      # DynamoDB: escribir en tabla de auditoría (problema actual)
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem"
        ]
        Resource = [
          aws_dynamodb_table.access_audit.arn
        ]
      },

      # Logs: CloudWatch
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

resource "aws_lambda_function" "ingest" {
  function_name = "${var.project_name}-ingest"
  role          = aws_iam_role.lambda_ingest_role.arn
  runtime       = "python3.11"
  handler       = "app.lambda_handler"

  filename         = "${path.module}/../lambda/ingest.zip"
  source_code_hash = filebase64sha256("${path.module}/../lambda/ingest.zip")

  environment {
    variables = {
      RAW_BUCKET            = var.raw_bucket_name
      LAB_RESULTS_QUEUE_URL = aws_sqs_queue.lab_results_queue.id
      LAB_RESULTS_TABLE     = aws_dynamodb_table.lab_results.name
      ACCESS_AUDIT_TABLE    = aws_dynamodb_table.access_audit.name
    }
  }
}


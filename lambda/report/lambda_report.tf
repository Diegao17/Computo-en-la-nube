########################################
# IAM ROLE para Lambda report
########################################

resource "aws_iam_role" "lambda_report_role" {
  name = "${var.project_name}-lambda-report-role"

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
    Name        = "${var.project_name}-lambda-report-role"
    Environment = var.environment
  }
}

########################################
# POLICY para Lambda report
########################################

resource "aws_iam_role_policy" "lambda_report_policy" {
  name = "${var.project_name}-lambda-report-policy"
  role = aws_iam_role.lambda_report_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # Permisos para leer desde DynamoDB (lab_results + patients)
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem"
        ]
        Resource = [
          aws_dynamodb_table.lab_results.arn,
          aws_dynamodb_table.patients.arn
        ]
      },
      # Permisos para escribir/leer objetos en S3 (report_bucket)
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject"
        ]
        # Usamos el bucket de raw como bucket de reportes también
        Resource = [
          "arn:aws:s3:::${var.raw_bucket_name}/*"
        ]
      },
      # Logs de CloudWatch
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
# LAMBDA report
########################################

resource "aws_lambda_function" "report" {
  function_name = "${var.project_name}-report"
  description   = "Lambda para generación de reportes PDF de resultados de laboratorio"

  # IMPORTANTE: crear el zip antes de apply:
  #   cd lambda/report
  #   zip report.zip app.py
  filename         = "${path.module}/lambda/report/report.zip"
  source_code_hash = filebase64sha256("${path.module}/lambda/report/report.zip")

  handler = "app.lambda_handler"
  runtime = "python3.12"

  role         = aws_iam_role.lambda_report_role.arn
  timeout      = 300
  memory_size  = 1024
  architectures = ["x86_64"]

  environment {
    variables = {
      REGION_NAME      = var.region
      LAB_RESULTS_TABLE = aws_dynamodb_table.lab_results.name
      PATIENTS_TABLE    = aws_dynamodb_table.patients.name
      # Usamos el mismo bucket que se usa para RAW (var.raw_bucket_name)
      REPORT_BUCKET    = var.raw_bucket_name
    }
  }

  tags = {
    Name        = "${var.project_name}-lambda-report"
    Environment = var.environment
  }
}

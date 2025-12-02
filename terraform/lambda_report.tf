resource "aws_iam_role" "lambda_report_role" {
  name = "${var.project_name}-lambda-report-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect    = "Allow",
      Principal = { Service = "lambda.amazonaws.com" },
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_report_basic" {
  role       = aws_iam_role.lambda_report_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# PERMISOS PARA LEER DYNAMODB Y ESCRIBIR EN S3
resource "aws_iam_role_policy" "lambda_report_policy" {
  name = "${var.project_name}-lambda-report-policy"
  role = aws_iam_role.lambda_report_role.id

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [

      # DynamoDB (leer resultados + insertar auditoría)
      {
        Effect = "Allow",
        Action = ["dynamodb:GetItem", "dynamodb:PutItem"],
        Resource = [
          aws_dynamodb_table.lab_results.arn,
          aws_dynamodb_table.access_audit.arn
        ]
      },

      # S3 (guardar PDFs + leer PDFs)
      {
        Effect   = "Allow",
        Action   = ["s3:PutObject", "s3:GetObject"],
        Resource = "arn:aws:s3:::${var.raw_bucket_name}/*"
      }
    ]
  })
}

# LAMBDA FUNCTION (REPORT PDF GENERATOR)
resource "aws_lambda_function" "report" {
  function_name = "${var.project_name}-report"
  role          = aws_iam_role.lambda_report_role.arn
  runtime       = "python3.11"
  handler       = "app.lambda_handler"

  # IMPORTANTE → RUTA ARREGLADA
  filename         = "${path.module}/../lambda/report.zip"
  source_code_hash = filebase64sha256("${path.module}/../lambda/report.zip")

  environment {
    variables = {
      LAB_RESULTS_TABLE  = aws_dynamodb_table.lab_results.name
      ACCESS_AUDIT_TABLE = aws_dynamodb_table.access_audit.name
      REPORTS_BUCKET     = var.raw_bucket_name
    }
  }

  depends_on = [
    aws_iam_role.lambda_report_role,
    aws_iam_role_policy.lambda_report_policy
  ]
}


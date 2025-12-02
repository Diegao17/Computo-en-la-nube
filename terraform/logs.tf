# Log group para el worker processor (ECS)
resource "aws_cloudwatch_log_group" "processor" {
  name              = "/ecs/${var.project_name}-processor"
  retention_in_days = 14
}

# Log group para el portal (ECS)
resource "aws_cloudwatch_log_group" "portal" {
  name              = "/ecs/${var.project_name}-portal"
  retention_in_days = 14
}

# Log group para Lambda de reportes
resource "aws_cloudwatch_log_group" "lambda_report" {
  name              = "/aws/lambda/${var.project_name}-report"
  retention_in_days = 14
}

########################################
# HTTP API (API Gateway v2) para LabSecure
# Proxy ANY /{proxy+} hacia Lambda ingest
########################################

resource "aws_apigatewayv2_api" "lab_http_api" {
  name          = "${var.project_name}-http-api"
  protocol_type = "HTTP"

  tags = {
    Name        = "${var.project_name}-http-api"
    Environment = var.environment
    Purpose     = "LabSecureHTTPAPI"
  }
}

########################################
# Integración Lambda (ingest)
########################################

resource "aws_apigatewayv2_integration" "lab_ingest_integration" {
  api_id                 = aws_apigatewayv2_api.lab_http_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.ingest.arn
  payload_format_version = "2.0"
}

########################################
# Ruta proxy ANY /{proxy+}
########################################

resource "aws_apigatewayv2_route" "proxy_route" {
  api_id    = aws_apigatewayv2_api.lab_http_api.id
  route_key = "ANY /{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.lab_ingest_integration.id}"
}

########################################
# Stage por defecto ($default)
########################################

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.lab_http_api.id
  name        = "$default"
  auto_deploy = true

  tags = {
    Name        = "${var.project_name}-http-api-default-stage"
    Environment = var.environment
  }
}

########################################
# Permiso para que el HTTP API invoque la Lambda
########################################

resource "aws_lambda_permission" "allow_invoke_from_http_api" {
  statement_id  = "AllowExecutionFromHTTPAPI"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ingest.arn
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.lab_http_api.execution_arn}/*/*"
}

########################################
# Output: endpoint del nuevo HTTP API
########################################

output "http_api_endpoint" {
  description = "Base URL for the HTTP API (use this as API_BASE_URL)"
  value       = aws_apigatewayv2_api.lab_http_api.api_endpoint
}

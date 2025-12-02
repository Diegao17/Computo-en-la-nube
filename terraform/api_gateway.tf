resource "aws_api_gateway_rest_api" "lab_api" {
  name = "${var.project_name}-api"
}

resource "aws_api_gateway_resource" "api" {
  rest_api_id = aws_api_gateway_rest_api.lab_api.id
  parent_id   = aws_api_gateway_rest_api.lab_api.root_resource_id
  path_part   = "api"
}

resource "aws_api_gateway_resource" "v1" {
  rest_api_id = aws_api_gateway_rest_api.lab_api.id
  parent_id   = aws_api_gateway_resource.api.id
  path_part   = "v1"
}

resource "aws_api_gateway_resource" "ingest" {
  rest_api_id = aws_api_gateway_rest_api.lab_api.id
  parent_id   = aws_api_gateway_resource.v1.id
  path_part   = "ingest"
}

resource "aws_api_gateway_method" "ingest_post" {
  rest_api_id   = aws_api_gateway_rest_api.lab_api.id
  resource_id   = aws_api_gateway_resource.ingest.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "ingest_post" {
  rest_api_id             = aws_api_gateway_rest_api.lab_api.id
  resource_id             = aws_api_gateway_resource.ingest.id
  http_method             = aws_api_gateway_method.ingest_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.ingest.invoke_arn
}

resource "aws_lambda_permission" "apigw_invoke_ingest" {
  statement_id  = "AllowAPIGatewayInvokeIngest"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ingest.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.lab_api.execution_arn}/*/*"
}

resource "aws_api_gateway_deployment" "lab_api_deploy" {
  rest_api_id = aws_api_gateway_rest_api.lab_api.id

  depends_on = [
    aws_api_gateway_method.ingest_post,
    aws_api_gateway_integration.ingest_post
  ]

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_api_gateway_stage" "lab_api_stage" {
  rest_api_id   = aws_api_gateway_rest_api.lab_api.id
  deployment_id = aws_api_gateway_deployment.lab_api_deploy.id
  stage_name    = "prod"
}


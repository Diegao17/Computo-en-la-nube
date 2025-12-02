resource "aws_cognito_user_pool" "labsecure_pool" {
  name = "${var.project_name}-user-pool"
}

resource "aws_cognito_user_pool_client" "labsecure_client" {
  name         = "${var.project_name}-user-pool-client"
  user_pool_id = aws_cognito_user_pool.labsecure_pool.id

  generate_secret = false

  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["openid", "email"]
  supported_identity_providers         = ["COGNITO"]

  callback_urls = ["http://localhost/callback"]
  logout_urls   = ["http://localhost/"]
}


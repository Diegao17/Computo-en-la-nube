########################################
# Cognito User Pool - LabSecure
########################################

resource "aws_cognito_user_pool" "labsecure_user_pool" {
  name = "${var.project_name}-user-pool"

  # Políticas de password (seguras pero razonables para demo)
  password_policy {
    minimum_length    = 8
    require_lowercase = true
    require_uppercase = true
    require_numbers   = true
    require_symbols   = false
  }

  # Auto-verificación por email (para entorno real)
  auto_verified_attributes = ["email"]

  # Atributos básicos que vamos a usar
  schema {
    name                     = "email"
    attribute_data_type      = "String"
    required                 = true
    developer_only_attribute = false
    mutable                  = true

    string_attribute_constraints {
      min_length = 5
      max_length = 128
    }
  }

  schema {
    name                     = "name"
    attribute_data_type      = "String"
    required                 = false
    developer_only_attribute = false
    mutable                  = true

    string_attribute_constraints {
      min_length = 1
      max_length = 64
    }
  }

  # Configuración de email básica (Cognito Hosted)
  email_configuration {
    email_sending_account = "COGNITO_DEFAULT"
  }

  # Etiquetas para identificar que es parte de LabSecure
  tags = {
    Project = var.project_name
    Role    = "auth"
  }
}

########################################
# Cognito User Pool Client - LabSecure Portal
########################################

resource "aws_cognito_user_pool_client" "labsecure_user_pool_client" {
  name         = "${var.project_name}-portal-client"
  user_pool_id = aws_cognito_user_pool.labsecure_user_pool.id

  # Para demo: sin secret, para SPA / front web
  generate_secret = false

  # Permitir flujo OAuth2 "code" (más seguro que implicit)
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["openid", "email", "profile"]

  supported_identity_providers = ["COGNITO"]

  # Callbacks pensados para el portal. En producción
  # puedes cambiarlos por el dominio real / CloudFront.
  callback_urls = [
    "http://localhost:8080/callback",
  ]

  logout_urls = [
    "http://localhost:8080/",
  ]

  # Para JWT basados en OAuth2 / OpenID Connect
  explicit_auth_flows = [
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
    "ALLOW_USER_SRP_AUTH"
  ]

  # Token lifetimes (demo razonable)
  access_token_validity  = 60  # minutos
  id_token_validity      = 60  # minutos
  refresh_token_validity = 30  # días

  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }
}

output "vpc_id" {
  description = "ID de la VPC"
  value       = aws_vpc.main.id
}

output "public_subnet_id" {
  description = "Subred pública"
  value       = aws_subnet.public_1.id
}

output "private_subnet_id" {
  description = "Subred privada"
  value       = aws_subnet.private_1.id
}

output "dynamodb_lab_results_table" {
  description = "Nombre de la tabla DynamoDB de resultados"
  value       = aws_dynamodb_table.lab_results.name
}

########################################
# Cognito Outputs
########################################

output "cognito_user_pool_id" {
  description = "ID del Cognito User Pool para autenticación de usuarios del portal"
  value       = aws_cognito_user_pool.labsecure_user_pool.id
}

output "cognito_user_pool_client_id" {
  description = "ID del Cognito User Pool Client usado por el portal"
  value       = aws_cognito_user_pool_client.labsecure_user_pool_client.id
}

output "cognito_user_pool_endpoint" {
  description = "Endpoint del User Pool, útil para validar JWT (issuer)"
  value       = aws_cognito_user_pool.labsecure_user_pool.endpoint
}

output "ec2_portal_public_ip" {
  description = "IP pública de la instancia EC2 del portal"
  value       = aws_instance.ec2_portal.public_ip
}

output "ec2_worker_public_ip" {
  description = "IP pública de la instancia EC2 del worker"
  value       = aws_instance.worker.public_ip
}

output "cognito_user_pool_domain" {
  value = aws_cognito_user_pool_domain.labsecure_user_pool_domain.domain
}

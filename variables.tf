variable "aws_region" {
  description = "Región AWS"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Nombre del proyecto"
  type        = string
  default     = "healthcare-lab"
}

variable "instance_type" {
  description = "Tipo de instancia EC2"
  type        = string
  default     = "t3.micro"
}

variable "key_name" {
  description = "Nombre del key pair de EC2 para SSH"
  type        = string
  default     = "healthcare-lab-worker-key"
}

variable "allowed_ssh_cidr" {
  description = "Rango CIDR desde donde podrás hacer SSH"
  type        = string
  default     = "0.0.0.0/0"
}

variable "raw_bucket_name" {
  description = "Nombre del bucket S3 donde se guardan los resultados crudos"
  type        = string
  default     = "healthcare-lab-lab-results-xqcn0m"
}

variable "environment" {
  description = "Deployment environment (e.g. dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "region" {
  description = "AWS region to deploy resources into"
  type        = string
  default     = "us-east-1"
}



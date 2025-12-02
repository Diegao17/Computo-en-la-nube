########################################
# TABLA: Resultados de laboratorio
########################################

resource "aws_dynamodb_table" "lab_results" {
  name         = "${var.project_name}-lab-results"
  billing_mode = "PAY_PER_REQUEST"

  # PK compuesta: result_id + patient_id
  hash_key  = "result_id"
  range_key = "patient_id"

  attribute {
    name = "result_id"
    type = "S"
  }

  attribute {
    name = "patient_id"
    type = "S"
  }

  # TTL para retención automática (7 años HIPAA) usando campo ttl_epoch
  ttl {
    attribute_name = "ttl_epoch"
    enabled        = true
  }

  tags = {
    Name        = "${var.project_name}-lab-results"
    Environment = var.environment
    Purpose     = "LabResults"
  }
}

########################################
# TABLA: Pacientes
########################################

resource "aws_dynamodb_table" "patients" {
  name         = "${var.project_name}-patients"
  billing_mode = "PAY_PER_REQUEST"

  hash_key = "patient_id"

  attribute {
    name = "patient_id"
    type = "S"
  }

  tags = {
    Name        = "${var.project_name}-patients"
    Environment = var.environment
    Purpose     = "Patients"
  }
}

########################################
# TABLA: Auditoría de accesos
########################################

resource "aws_dynamodb_table" "access_audit" {
  name         = "${var.project_name}-access-audit"
  billing_mode = "PAY_PER_REQUEST"

  hash_key  = "audit_id"
  range_key = "timestamp"

  # Clave primaria
  attribute {
    name = "audit_id"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "S"
  }

  # Atributos usados en GSIs
  attribute {
    name = "patient_id"
    type = "S"
  }

  attribute {
    name = "actor_id"
    type = "S"
  }

  # GSI para buscar por patient_id
  global_secondary_index {
    name            = "by_patient"
    hash_key        = "patient_id"
    projection_type = "ALL"
  }

  # GSI para buscar por actor (usuario / sistema)
  global_secondary_index {
    name            = "by_actor"
    hash_key        = "actor_id"
    projection_type = "ALL"
  }

  tags = {
    Name        = "${var.project_name}-access-audit"
    Environment = var.environment
    Purpose     = "Audit"
  }
}



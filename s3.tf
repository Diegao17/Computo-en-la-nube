
# S3 BUCKET PARA RESULTADOS DE LAB
# (RAW + PROCESSED + REPORTS)
########################################

resource "random_string" "suffix" {
  length  = 6
  upper   = false
  special = false
}

# Bucket principal donde se guardan:
# - JSON crudos de la Lambda de ingest (raw/)
# - JSON procesados por el worker (processed/)
# - "PDFs" generados por la Lambda report (reports/)
#
# Usamos var.raw_bucket_name si ya la tienes definida,
# si no, puedes cambiar directamente el valor del bucket aquí.
resource "aws_s3_bucket" "lab_results" {
  bucket = var.raw_bucket_name

  tags = {
    Name = "${var.project_name}-lab-results"
  }
}

# Bloquear acceso público (requisito de seguridad / LabSecure)
resource "aws_s3_bucket_public_access_block" "lab_results_block" {
  bucket                  = aws_s3_bucket.lab_results.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Cifrado por defecto del bucket (encryption at rest)
resource "aws_s3_bucket_server_side_encryption_configuration" "lab_results_enc" {
  bucket = aws_s3_bucket.lab_results.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# (Opcional pero profesional) Versionado
resource "aws_s3_bucket_versioning" "lab_results_versioning" {
  bucket = aws_s3_bucket.lab_results.id

  versioning_configuration {
    status = "Enabled"
  }
}


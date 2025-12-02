resource "aws_sns_topic" "lab_results_ready" {
  name = "${var.project_name}-lab-results-ready"

  tags = {
    Name        = "${var.project_name}-lab-results-ready"
    Environment = var.environment
    Purpose     = "LabResultsNotification"
  }
}

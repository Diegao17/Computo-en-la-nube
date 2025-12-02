resource "aws_sqs_queue" "lab_results_dlq" {
  name = "${var.project_name}-lab-results-dlq"
}

resource "aws_sqs_queue" "lab_results_queue" {
  name                       = "${var.project_name}-lab-results-queue"
  visibility_timeout_seconds = 60

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.lab_results_dlq.arn
    maxReceiveCount     = 5
  })
}

resource "aws_sqs_queue" "notify_dlq" {
  name = "${var.project_name}-notify-dlq"
}

resource "aws_sqs_queue" "notify_queue" {
  name                       = "${var.project_name}-notify-queue"
  visibility_timeout_seconds = 60

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.notify_dlq.arn
    maxReceiveCount     = 5
  })
}


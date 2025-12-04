# LabSecure – Healthcare Lab Results Platform (Scenario F)

LabSecure is a secure, end-to-end platform for ingesting, processing, storing, and presenting healthcare lab results. It is designed for Scenario F – environments that require strong security, auditability, and alignment with regulatory requirements such as HIPAA/GDPR.

The platform includes:

- Lab results ingestion via API (API Gateway + Lambda).
- Asynchronous processing pipeline (SQS + S3 + EC2 Worker + DynamoDB).
- Patient portal to view results and download PDF reports.
- Notification pipeline when results are ready.
- Full logging and audit trails via CloudWatch.
- Infrastructure as Code using Terraform.

---

## 1. Repository Structure

```text
healthcare-lab-platform / LabSecure
├── README.md                  # This file
├── ARCHITECTURE.md            # Architecture & design decisions
├── terraform/                 # Terraform IaC for all infrastructure
│   ├── main.tf
│   ├── vpc.tf
│   ├── dynamodb.tf (or rds.tf)
│   ├── ec2.tf (or ecs.tf)
│   ├── lambda.tf
│   ├── cognito.tf
│   ├── s3.tf
│   ├── sqs.tf
│   ├── variables.tf
│   ├── outputs.tf
│   └── README.md
├── lambda/
│   ├── ingest/                # Ingest API Lambda
│   ├── notify/                # Notification Lambda (SQS → SNS/SES)
│   ├── report/                # Report generation Lambda (PDFs)
│   └── data_lifecycle/        # Optional data lifecycle Lambda (GDPR/HIPAA)
├── services/
│   ├── processor/             # EC2 worker service (SQS → S3 → DynamoDB)
│   │   ├── Dockerfile (optional)
│   │   ├── requirements.txt
│   │   └── worker.py
│   └── portal/                # Patient portal web app
│       ├── Dockerfile (optional)
│       ├── requirements.txt
│       └── app.py
├── scripts/
│   ├── data_generator.py      # Test data generator script
│   └── test_api.sh            # Simple API tests via curl
├── tests/
│   ├── unit/
│   └── integration/
├── .github/
│   └── workflows/
│       └── deploy.yml         # CI/CD pipeline (lint, test, deploy)
└── docs/
    ├── setup.md               # Detailed setup and deployment
    ├── api.md                 # API documentation
    └── cost_analysis.md       # Detailed cost breakdown

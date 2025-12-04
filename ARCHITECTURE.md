# LabSecure – Architecture and Design Decisions

## 1. Overview

LabSecure is a secure healthcare lab results processing platform designed for Scenario F(high-security, regulated environments such as HIPAA/GDPR). The system implements an end-to-end workflow:

- Ingest lab results from external lab systems via API.
- Validate, normalize, and enrich the data.
- Store raw and processed data securely with full auditability.
- Expose a patient portal to view results and download reports.
- Notify patients when their lab results are ready.
- Enforce strict security, logging, and least-privilege access.

The platform is built entirely on AWS using Infrastructure as Code (Terraform) and follows an event-driven, decoupled architecture.

---

## 2. High-Level Architecture

> The actual diagram is maintained in the docs folder (image.png).

### 2.1 Components

- **API Gateway**
  - Public HTTPS entrypoint for external lab systems.
  - Exposes `/api/v1/ingest`, `/api/v1/health`, `/api/v1/status/{result_id}`.

- **Lambda – Ingest**
  - Validates incoming payloads.
  - Writes raw payloads to S3.
  - Sends messages to the Lab Results SQS Queue.
  - Logs all requests and responses to CloudWatch Logs.

- **S3 – Raw & Reports Buckets**
  - `raw-lab-results` bucket:
    - Stores the raw JSON uploaded by ingest Lambda.
  - `lab-reports` bucket:
    - Stores generated PDF reports.
  - Both buckets use server-side encryption and blocked public access.

- **SQS – Lab Results Queue + DLQ**
  - Main queue for unprocessed lab results.
  - Worker polls this queue using long polling.
  - Messages that repeatedly fail go to a Dead Letter Queue (DLQ).

- **EC2 Worker (Processor Service)**
  - Deployed in a **private subnet**.
  - Continuously polls SQS.
  - Fetches corresponding raw payload from S3.
  - Validates and normalizes lab results.
  - Stores processed data in DynamoDB.
  - Pushes a message into Notification SQS Queue to trigger notifications.
  - Emits metrics and logs to CloudWatch.

- **DynamoDB**
  - Primary storage for:
    - Patients
    - Lab results
    - Status and metadata
  - Fully encrypted and managed.

- **SQS – Notification Queue**
  - Receives events when a result transitions to “READY”.
  - Triggers the **Notify Lambda**.

- **Lambda – Notify**
  - Consumes from the notification queue.
  - Uses **SNS or SES** to send email notifications to patients.
  - Stores notification status in DynamoDB.
  - Logs to CloudWatch.

- **Lambda – Report**
  - Generates a PDF report for a given `result_id`.
  - Reads data from DynamoDB.
  - Renders a report and stores it in S3 (`lab-reports`).
  - Returns a pre-signed URL with 1-hour expiry.

- **Cognito User Pool**
  - Handles patient authentication.
  - The patient portal uses Cognito-hosted login or OAuth flows.
  - API Gateway and the portal can validate JWT tokens from Cognito.

- **Patient Portal (services/portal)**
  - Web application (Flask / Python in this project) running on EC2 or behind an ALB.
  - Deployed in a private subnet and exposed via an Application Load Balancer (ALB).
  - Uses Cognito for authentication (OIDC/JWT).
  - Exposes:
    - `/login` – redirects to Cognito.
    - `/dashboard` – lists all results for the authenticated patient.
    - `/results/{result_id}` – detailed view, including abnormal indicators.
    - `/profile` – patient information.
    - `/health` – health check endpoint for ALB.

- **CloudWatch**
  - Centralized logging for Lambda, EC2 services, and API Gateway access logs.
  - Metrics and alarms for:
    - SQS queue depth
    - Lambda errors
    - EC2 instance health

- **Terraform**
  - All infrastructure is defined under `terraform/`.
  - Provides reproducible environments and versioned infrastructure.

---

## 3. Decision 1 – Database Choice (RDS vs DynamoDB)

### 3.1 Options

- **Option A – RDS (Relational Database Service)**
  - Advantages:
    - Strong relational modeling and SQL support.
    - Transactions and complex joins.
    - Familiar to many developers.
  - Disadvantages:
    - Requires capacity planning (instance size, storage).
    - Requires managing backups, patching windows, and availability.
    - Higher baseline cost for always-on instances.
    - Scaling write throughput is more complex.

- **Option B – DynamoDB (Chosen)**
  - Advantages:
    - Fully managed, serverless, no instance management.
    - Automatic scaling based on traffic.
    - Very low latency reads and writes.
    - Flexible schema fits diverse lab test structures.
    - Integrated encryption and IAM-based access.
  - Disadvantages:
    - No complex joins; queries must be designed around access patterns.
    - Limited ad-hoc querying compared to SQL.
    - Requires careful key design (PK/SK) and indexes.

### 3.2 Decision

We chose DynamoDB as the primary data store for patients and lab results.

### 3.3 Trade-offs Considered

- The system needs to query results by:
  - `patient_id` (for dashboards).
  - `result_id` (for status and details).
- The schema for different test panels (CBC, CMP, lipid panel, thyroid panel, etc.) is highly variable.
- The workload is event-driven, spiky, and read-heavy from the portal.

Relational features (complex joins, multi-row transactions) are not critical for this use case, while scalability, low ops overhead, and costs are more important.

### 3.4 Cost Comparison (Approximate)

For a moderate workload (~50k writes and ~50k reads per month, ~1–2 GB of data):

- **RDS (e.g., t3.micro, Multi-AZ)**
  - Monthly instance cost + storage + backups.
  - Typical range: ~$40–$80/month baseline, regardless of traffic.

- **DynamoDB (On-Demand / Provisioned with autoscaling)**
  - Pay per read, write, and storage.
  - For the same workload, typically a few dollars per month, especially under on-demand/event-driven patterns.

### 3.5 Final Justification

DynamoDB was selected because:

- It matches the access patterns required by the portal and APIs.
- It significantly reduces operational complexity (no patching, no backups management).
- It is more cost-efficient for a spiky, event-driven workload.
- It aligns well with serverless and managed services used throughout the architecture.

---

## 4. Decision 2 – Compute for Processing Workers

### 4.1 Options

- **Option A – ECS on EC2**
  - Pros: container orchestration, multiple services per cluster, good for microservices.
  - Cons: requires managing the ECS cluster, capacity, and EC2 nodes.

- **Option B – ECS on Fargate**
  - Pros: fully managed compute, no servers to manage, scales per-task.
  - Cons: higher cost per vCPU/GB than EC2 if running 24/7, limited control over underlying OS.

- **Option C – EC2 with custom scripts (Chosen)**
  - Pros:
    - Simple and easy to reason about.
    - Full control over OS, Python environment, and worker process.
    - Direct and predictable integration with SQS.
  - Cons:
    - We are responsible for OS patching and instance management.
    - Scaling is manual/through autoscaling groups, not per-task.

### 4.2 Decision

We chose to run the worker as a Python service on a dedicated EC2 instance, deployed in a private subnet and managed via Terraform.

### 4.3 Trade-offs

- **Simplicity vs. Flexibility**
  - For a single background worker, ECS/Fargate would add complexity without delivering strong benefits.
  - EC2 keeps the operational model straightforward: one instance, one worker process, one IAM role.

- **Cost**
  - A small EC2 instance (e.g., t3.small / t3.micro) running 24/7 is often cheaper than a Fargate task running continuously.
  - ECS/Fargate shines in bursty multi-service environments, which is more than what this project requires.

### 4.4 Cost Comparison (Approximate)

- **EC2 (t3.small)**
  - 24/7 usage: roughly $15–$25/month compute, plus EBS storage.

- **ECS on Fargate (1 vCPU, 2 GB RAM 24/7)**
  - 24/7 usage typically higher (~$30+ per month at similar capacity).

The project prioritizes simplicity and cost-effectiveness, which favors EC2 for this single worker.

### 4.5 Final Justification

EC2 was chosen because:

- It is sufficient for a single, long-running worker.
- It meets Scenario F requirements (private subnet, IAM role, no public IP).
- It avoids the overhead of managing ECS tasks and clusters.
- It offers a clear and easily explainable operational model.

---

## 5. Decision 3 – Authentication Strategy (Cognito)

### 5.1 Options

1. **Cognito User Pools only (Chosen)**
   - Direct username/password or email/password login.
   - JWT tokens for authentication in the portal.

2. **Cognito User Pools + Identity Pools**
   - Adds fine-grained AWS resource access per user (temporary AWS credentials).
   - More complex setup.

3. **Cognito with Social Identity Providers**
   - Integration with Google/Facebook/etc.
   - Not required in a clinical lab environment.

### 5.2 Decision

We use Cognito User Pools only to authenticate patients.

- The patient portal validates the JWT access/ID tokens issued by Cognito.
- Backend APIs can use Cognito authorizers for protected endpoints.

### 5.3 Final Justification

- Simple, robust authentication mechanism.
- Social logins are not aligned with a more controlled, clinical environment.
- Identity Pools (direct AWS access per user) are not necessary; all backend access is via Lambda/EC2 with IAM roles.

---

## 6. Data Flow

### 6.1 End-to-End Flow

1. **Ingestion**
   - External lab system sends a POST request to `/api/v1/ingest`.
   - API Gateway forwards the request to the ingest Lambda.
   - Lambda validates the JSON structure and required fields:
     - `patient_id`, `lab_id`, `test_type`, `results`, etc.
   - If valid:
     - The raw payload is stored in the S3 raw results bucket.
     - An entry is written to SQS lab-results queue with metadata and S3 object key.
     - A `result_id` is returned to the caller.
   - If invalid:
     - Lambda returns a 4xx response with an error description.
     - Error is logged in CloudWatch.

2. **Processing**
   - The EC2 worker continuously long-polls SQS.
   - On message receipt:
     - It fetches the raw JSON from S3.
     - Parses tests and normalizes values (CBC, CMP, lipid panel, thyroid panel).
     - Calculates abnormal flags and status.
     - Writes normalized data to DynamoDB (e.g., partitioned by `patient_id`, sorted by `result_id`).
     - Updates processing status in DynamoDB.
     - Sends a message to the notification queue.
   - On unrecoverable error:
     - The message is eventually moved to the DLQ.
     - The error is logged and can be inspected manually.

3. **Notification**
   - The notify Lambda is triggered via SQS event.
   - It looks up patient contact information in DynamoDB.
   - It sends an email (or SMS) using SNS/SES indicating that results are available.
   - It records notification status (success/failure) and logs to CloudWatch.

4. **Report Generation**
   - When the patient requests a PDF (from the portal):
     - The portal calls the report Lambda.
     - Lambda fetches the result details from DynamoDB.
     - A PDF is generated (e.g., using a templating engine) and stored in S3.
     - A pre-signed URL with a 1-hour TTL is returned.
   - The portal exposes this URL to the patient for download.

5. **Patient Portal**
   - The patient authenticates via Cognito on `/login`.
   - After login:
     - `/dashboard` lists all lab results for that patient (by querying DynamoDB).
     - `/results/{result_id}` shows detailed information, including abnormal markers.
     - `/profile` displays basic demographic data.
   - All portal API calls are authenticated via Cognito JWT tokens and executed on behalf of the authenticated user.

---

## 7. Error Handling, Retries, and DLQs

- **Ingest Lambda**
  - Returns appropriate HTTP error codes:
    - `400` for validation errors.
    - `500` for internal errors.
  - Uses CloudWatch for error logs.

- **SQS + Worker**
  - Worker uses long polling with visibility timeouts.
  - If processing fails:
    - The message becomes visible again and is retried.
    - After a configured number of attempts, the message is sent to the DLQ.

- **Notify Lambda**
  - Uses exponential backoff and retry on transient errors (network, SES/SNS).
  - Logs failures and, if necessary, can push messages to a notification DLQ.

- **Report Lambda**
  - Handles timeouts and invalid `result_id` values gracefully.
  - Returns meaningful errors to the portal and logs full stack traces to CloudWatch.

---

## 8. Security Model

### 8.1 Encryption

- **At Rest**
  - S3 buckets use server-side encryption (SSE-S3 or SSE-KMS).
  - DynamoDB tables are encrypted with KMS.
  - SQS queues are encrypted.
  - EBS volumes for EC2 instances can be encrypted via KMS.

- **In Transit**
  - All external access is via HTTPS through API Gateway and the ALB.
  - Internal service-to-service communication within the VPC occurs over private subnets.

### 8.2 Network Isolation

- **VPC**
  - Public subnets:
    - ALB
    - NAT Gateway
  - Private subnets:
    - EC2 worker
    - Portal service
    - Lambdas (via VPC configuration where needed)

- **Security Groups**
  - EC2 instances:
    - Allow only required inbound traffic (e.g., from ALB or SSH for admin).
    - Allow outbound traffic to SQS, S3, DynamoDB via NAT or VPC endpoints.
  - ALB:
    - Allows inbound HTTPS/HTTP from the internet.
    - Forwards traffic only to target groups (portal).

### 8.3 Access Control (IAM)

- Each component has a dedicated IAM Role following least-privilege principles:
  - **Ingest Lambda Role**
    - `s3:PutObject` to the raw bucket.
    - `sqs:SendMessage` to the lab results queue.
  - **Worker EC2 Role**
    - `sqs:ReceiveMessage`, `DeleteMessage` on the lab queue.
    - `s3:GetObject` on the raw bucket.
    - `dynamodb:PutItem`, `UpdateItem`, `Query` on lab results table.
    - `sqs:SendMessage` to the notification queue.
  - **Notify Lambda Role**
    - `sqs:ReceiveMessage` on notification queue.
    - `ses:SendEmail` or `sns:Publish`.
    - `dynamodb:UpdateItem` for notification status.
  - **Report Lambda Role**
    - `dynamodb:GetItem`/`Query` for lab results.
    - `s3:PutObject` on reports bucket.
    - `s3:GetObject` for generating pre-signed URLs.

### 8.4 Auditing and Logging

- All access to sensitive data is logged through:
  - **CloudWatch Logs** (Lambda, EC2, Worker).
  - **API Gateway Access Logs**.
- Application-level audit trails can be stored in DynamoDB (e.g., who accessed which result and when).

---

## 9. Scalability and Reliability

- **Scalability**
  - Ingest API scales via Lambda + API Gateway.
  - DynamoDB auto-scales read/write capacity.
  - SQS buffers spikes ensuring the worker is not overwhelmed.
  - The worker EC2 instance can be placed in an Auto Scaling Group if needed.

- **Reliability**
  - Use of DLQs prevents data loss on repeated failures.
  - Separation of concerns (ingest vs processing vs notification) avoids cascading failures.
  - Health checks on ALB and `/health` endpoints ensure only healthy instances receive traffic.

---

## 10. Cost Considerations (Summary)

- **Core Services**
  - API Gateway + Lambda: pay-per-request, cost-efficient for sporadic lab submissions.
  - DynamoDB: pay-per-request + storage, low admin overhead.
  - S3: low-cost storage for raw and report files.
  - EC2 worker: small always-on cost, but predictable and simpler setup.

- **Optimization Strategies**
  - Use VPC endpoints to reduce NAT Gateway data processing costs if needed.
  - Use DynamoDB On-Demand for unpredictable workloads or Provisioned with autoscaling for stable ones.
  - Right-size EC2 instances and consider spot or schedule-based scaling if applicable.
  - Archive old raw data (e.g., S3 Glacier) for long-term retention.

This architecture balances security, operational simplicity, cost-efficiency, and scalability, matching the requirements of Scenario F.

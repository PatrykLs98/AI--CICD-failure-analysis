# AI--CI/CD-failure-analysis
A serverless and event-driven solution that collects metadata from CI/CD process and then uses AI tools to identify the cause of failures.
# Architecture
GitHub
  ↓
CodePipeline
  ↓
CodeBuild
  ↓ failure event
EventBridge
  ↓
Lambda: Incident Collector
  ├─ reads logs from CloudWatch
  ├─ calls Amazon Bedrock
  ↓
S3: failed-events/*.json
  ↓ S3 ObjectCreated
Lambda: Analytics
  ├─ writes analytics/failure-summary.json
  ↓
S3: dashboard/index.html
# Docs
Personal notes about project and its future development.
# Examples
Examples JSON files and screenshots from the project tests
# Lambdas
Lambda functions are designed to detect errors in CodePipeline / CodeBuild, retrieve logs from CloudWatch, classify the error cause, generate AI recommendations using Amazon Bedrock, save incidents in an S3 Bucket and build an HTML dashboard report.
# Sample-app
Example application files used for testing, analyzing and detecting different CI/CD failures.
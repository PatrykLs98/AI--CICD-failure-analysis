The project uses an event-driven serverless architecture on AWS.

1. A commit pushed to GitHub triggers AWS CodePipeline.
2. CodePipeline starts a CodeBuild project.
3. If the build fails, CodePipeline emits an event to EventBridge.
4. EventBridge invokes the Incident Collector Lambda.
5. The Lambda retrieves CodeBuild logs from CloudWatch Logs.
6. The failure is classified using rule-based logic.
7. Amazon Bedrock generates an explanation and remediation recommendation.
8. The incident is stored in S3 as a JSON file.
9. S3 ObjectCreated event triggers the Analytics Lambda.
10. Analytics Lambda aggregates incidents and generates:
   - `analytics/failure-summary.json`
   - `dashboard/index.html`
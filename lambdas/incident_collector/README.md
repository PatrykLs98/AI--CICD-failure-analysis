This Lambda function receives FAILED build event then extracts build_id. After that steps it retrieves Codebuild logs from CloudWatch, classifies root cause and then sends logs/details to Amazon Bedrock. At the end stores incident JSON in S3 Bucket.
# Note
Every sensitive data was hidden in this file.
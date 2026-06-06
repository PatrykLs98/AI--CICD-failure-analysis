## What is not included in this repository for own safety

This repository does not include:

- AWS credentials
- access keys
- secret keys
- real AWS account IDs
- private ARNs
- real production logs
- sensitive environment variables

## Configuration

Values such as S3 bucket names, Bedrock model IDs and other environment-specific settings should be configured through Lambda environment variables.

Example:

```txt
BUCKET_NAME=<your-s3-bucket-name>
BEDROCK_MODEL_ID=<your-bedrock-model-or-inference-profile-id>
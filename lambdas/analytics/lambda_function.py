import json
import os
import boto3
import datetime
from botocore.exceptions import ClientError

s3 = boto3.client("s3")
codebuild = boto3.client("codebuild")
logs = boto3.client("logs")
bedrock = boto3.client("bedrock-runtime")

BUCKET_NAME = os.environ.get("BUCKET_NAME")


def s3_object_exists(bucket, key):
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            return False
        raise


def classify_error(text):
    text = text.lower()

    if "modulenotfounderror" in text or "no module named" in text:
        return "PYTHON_IMPORT_ERROR"

    elif "no matching distribution found" in text:
        return "DEPENDENCY_ERROR"

    elif "could not find a version that satisfies the requirement" in text:
        return "DEPENDENCY_ERROR"

    elif "accessdenied" in text or "not authorized" in text:
        return "IAM_ERROR"

    elif "exit status 127" in text or "command not found" in text:
        return "INVALID_COMMAND"

    elif "timeout" in text or "timed out" in text:
        return "TIMEOUT"

    elif "pytest" in text or "failed test" in text:
        return "TEST_FAILURE"

    elif "command_execution_error" in text:
        return "BUILD_COMMAND_ERROR"

    return "UNKNOWN"


def extract_error_details(text, root_cause):
    lines = text.splitlines()

    if root_cause == "DEPENDENCY_ERROR":
        for line in lines:
            line_lower = line.lower()

            if "no matching distribution found" in line_lower:
                return line.strip()

            if "could not find a version that satisfies the requirement" in line_lower:
                return line.strip()

    if root_cause == "PYTHON_IMPORT_ERROR":
        for line in lines:
            if "ModuleNotFoundError" in line or "No module named" in line:
                return line.strip()

    if root_cause == "INVALID_COMMAND":
        for line in lines:
            if "command not found" in line.lower() or "exit status 127" in line.lower():
                return line.strip()

    if root_cause == "IAM_ERROR":
        for line in lines:
            if "AccessDenied" in line or "not authorized" in line:
                return line.strip()

    if root_cause == "TEST_FAILURE":
        for line in lines:
            if "FAILED" in line and ".py" in line:
                return line.strip()

    return "No detailed error found"


def detect_signals(text):
    text_lower = text.lower()
    signals = []

    if "no matching distribution found" in text_lower:
        signals.append("missing python package detected")

    if "could not find a version that satisfies the requirement" in text_lower:
        signals.append("invalid dependency detected")

    if "modulenotfounderror" in text_lower or "no module named" in text_lower:
        signals.append("python import error detected")

    if "exit status 127" in text_lower or "command not found" in text_lower:
        signals.append("invalid command detected")

    if "accessdenied" in text_lower or "not authorized" in text_lower:
        signals.append("aws permission issue detected")

    if "build timed out" in text_lower or "timed out" in text_lower:
        signals.append("timeout detected")

    if "failed test" in text_lower or "failed " in text_lower and ".py::" in text_lower:
        signals.append("pytest test failure detected")

    if "command_execution_error" in text_lower:
        signals.append("codebuild command execution error detected")

    return signals


def generate_ai_analysis(root_cause, error_details, log_excerpt):
    prompt = f"""
You are a DevOps CI/CD assistant.

Analyze this AWS CodeBuild failure and return raw JSON with:
- explanation
- recommendation

Root cause category: {root_cause}
Error details: {error_details}

Log excerpt:
{log_excerpt}

Return only raw JSON.
Do not use markdown.
Do not wrap the response in ```json.
"""

    response = bedrock.converse(
        modelId=os.environ.get("BEDROCK_MODEL_ID"),
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "text": prompt
                    }
                ]
            }
        ],
        inferenceConfig={
            "maxTokens": 300,
            "temperature": 0.2
        }
    )

    text = response["output"]["message"]["content"][0]["text"]

    return parse_ai_response(text)


def get_codebuild_logs(build_id):
    if not build_id:
        return ""

    build_response = codebuild.batch_get_builds(
        ids=[build_id]
    )

    builds = build_response.get("builds", [])

    if not builds:
        print("No CodeBuild build found")
        return ""

    build = builds[0]
    log_info = build.get("logs", {})

    group_name = log_info.get("groupName")
    stream_name = log_info.get("streamName")

    print("LOG GROUP:", group_name)
    print("LOG STREAM:", stream_name)

    if not group_name or not stream_name:
        return ""

    log_response = logs.get_log_events(
        logGroupName=group_name,
        logStreamName=stream_name,
        startFromHead=True
    )

    messages = []

    for log_event in log_response.get("events", []):
        messages.append(log_event.get("message", ""))

    return "\n".join(messages)


def parse_ai_response(text):
    text = text.strip()

    if text.startswith("```"):
        text = text.replace("```json", "")
        text = text.replace("```", "")
        text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "explanation": text,
            "recommendation": "Review CodeBuild logs and verify the build configuration."
        }


def handler(event, context):
    detail = event.get("detail", {})

    state = detail.get("state")
    stage = detail.get("stage")

    if not (stage == "Build" and state == "FAILED"):
        print("IGNORED - not Build FAILED")
        return

    execution_result = detail.get("execution-result", {})
    summary = execution_result.get("external-execution-summary", "")
    build_id = execution_result.get("external-execution-id")

    if not build_id:
        print("No build_id found, skipping")
        return

    safe_build_id = build_id.replace(":", "_").replace("/", "_")
    key = f"failed-events/{safe_build_id}.json"

    if s3_object_exists(BUCKET_NAME, key):
        print("Incident already exists, skipping duplicate build:", build_id)
        return

    full_logs = get_codebuild_logs(build_id)

    text_for_classification = summary + "\n" + full_logs

    root_cause = classify_error(text_for_classification)
    error_details = extract_error_details(text_for_classification, root_cause)
    detected_signals = detect_signals(text_for_classification)

    try:
        ai_analysis = generate_ai_analysis(
            root_cause,
            error_details,
            full_logs[-3000:]
        )
    except Exception as e:
        print("Bedrock error:", str(e))
        ai_analysis = {
            "explanation": "AI analysis unavailable.",
            "recommendation": "Review CodeBuild logs manually."
        }

    incident = {
        "pipeline": detail.get("pipeline"),
        "stage": detail.get("stage"),
        "state": state,
        "build_id": build_id,
        "root_cause": root_cause,
        "error_details": error_details,
        "detected_signals": detected_signals,
        "ai_explanation": ai_analysis.get("explanation"),
        "ai_recommendation": ai_analysis.get("recommendation"),
        "log_excerpt": full_logs[-3000:],
        "timestamp": datetime.datetime.utcnow().isoformat()
    }

    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=key,
        Body=json.dumps(incident, indent=2),
        ContentType="application/json"
    )

    print("FAILED BUILD DETECTED")
    print("PIPELINE:", detail.get("pipeline"))
    print("STAGE:", detail.get("stage"))
    print("ROOT CAUSE:", root_cause)
    print("ERROR DETAILS:", error_details)
    print("AI ANALYSIS GENERATED")
    print("Saved incident to S3", key)

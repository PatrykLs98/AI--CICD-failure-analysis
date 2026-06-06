import os
import json
import boto3
import datetime
from collections import Counter, defaultdict

s3 = boto3.client("s3")

BUCKET_NAME = os.environ.get("BUCKET_NAME")


def generate_html_dashboard(summary):
    by_root_cause = summary.get("by_root_cause", {})
    top_signals = summary.get("top_signals", {})
    examples = summary.get("examples", {})
    ai_examples = summary.get("ai_examples", {})

    root_cause_rows = ""
    ai_html = ""

    for root_cause, items in ai_examples.items():
        ai_html += f"<h3>{root_cause}</h3>"

        for item in items:
            explanation = item.get("explanation", "")
            recommendation = item.get("recommendation", "")

            ai_html += f"""
            <div class="ai-box">
                <p><strong>Explanation:</strong> {explanation}</p>
                <p><strong>Recommendation:</strong> {recommendation}</p>
            </div>
            """

    for root_cause, count in by_root_cause.items():
        root_cause_rows += f"""
        <tr>
            <td>{root_cause}</td>
            <td>{count}</td>
        </tr>
        """

    signal_rows = ""

    for signal, count in top_signals.items():
        signal_rows += f"""
        <tr>
            <td>{signal}</td>
            <td>{count}</td>
        </tr>
        """

    examples_html = ""

    for root_cause, example_list in examples.items():
        examples_html += f"<h3>{root_cause}</h3><ul>"

        for example in example_list:
            examples_html += f"<li>{example}</li>"

        examples_html += "</ul>"

    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>CI/CD Failure Dashboard</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 40px;
            background-color: #f5f5f5;
        }}

        h1 {{
            color: #222;
        }}

        .card {{
            background: white;
            padding: 20px;
            margin-bottom: 20px;
            border-radius: 8px;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
        }}

        th, td {{
            padding: 10px;
            border-bottom: 1px solid #ddd;
            text-align: left;
        }}

        th {{
            background-color: #eee;
        }}

        .total {{
            font-size: 28px;
            font-weight: bold;
        }}

        code {{
            background: #eee;
            padding: 2px 5px;
            border-radius: 4px;
        }}
        .ai-box {{
            background: #f9fafb;
            border-left: 4px solid #444;
            padding: 12px;
            margin-bottom: 12px;
            border-radius: 4px;
        }}
    </style>
</head>
<body>

    <h1>CI/CD Failure Dashboard</h1>

    <div class="card">
        <h2>Summary</h2>
        <p>Generated at: <code>{summary.get("generated_at")}</code></p>
        <p>Total failures:</p>
        <p class="total">{summary.get("total_failures")}</p>
    </div>

    <div class="card">
        <h2>Failures by Root Cause</h2>
        <table>
            <tr>
                <th>Root Cause</th>
                <th>Count</th>
            </tr>
            {root_cause_rows}
        </table>
    </div>

    <div class="card">
        <h2>Top Detected Signals</h2>
        <table>
            <tr>
                <th>Signal</th>
                <th>Count</th>
            </tr>
            {signal_rows}
        </table>
    </div>

    <div class="card">
        <h2>Error Examples</h2>
        {examples_html}
    </div>
    <div class="card">
        <h2>AI Recommendations</h2>
        {ai_html}
    </div>

</body>
</html>
"""
    return html


def handler(event, context):
    response = s3.list_objects_v2(
        Bucket=BUCKET_NAME,
        Prefix="failed-events/"
    )

    if "Contents" not in response:
        print("No failed events found")
        return

    signal_counter = Counter()
    counter = Counter()
    examples = defaultdict(list)
    ai_examples = defaultdict(list)
    seen_build_ids = set()

    for obj in response["Contents"]:
        key = obj["Key"]

        if key.endswith("/") or not key.endswith(".json"):
            continue

        file_obj = s3.get_object(
            Bucket=BUCKET_NAME,
            Key=key
        )

        content = file_obj["Body"].read()
        data = json.loads(content.decode("utf-8"))

        build_id = data.get("build_id")

        if build_id:
            if build_id in seen_build_ids:
                print("SKIPPING DUPLICATE BUILD:", build_id)
                continue
            seen_build_ids.add(build_id)

        root_cause = data.get("root_cause", "UNKNOWN")
        error_details = data.get("error_details", "No details")
        detected_signals = data.get("detected_signals", [])
        ai_explanation = data.get("ai_explanation")
        ai_recommendation = data.get("ai_recommendation")

        print("COUNTED FILE:", key)
        print("BUILD ID:", build_id)
        print("ROOT CAUSE:", root_cause)

        counter[root_cause] += 1

        for signal in detected_signals:
            signal_counter[signal] += 1

        if (
            error_details != "No details"
            and error_details not in examples[root_cause]
            and len(examples[root_cause]) < 3
        ):
            examples[root_cause].append(error_details)

        if ai_explanation and ai_recommendation and len(ai_examples[root_cause]) < 1:
            ai_examples[root_cause].append({
                "explanation": ai_explanation,
                "recommendation": ai_recommendation
            })

    summary = {
        "generated_at": datetime.datetime.utcnow().isoformat(),
        "total_failures": sum(counter.values()),
        "by_root_cause": dict(counter),
        "top_signals": dict(signal_counter),
        "examples": dict(examples),
        "ai_examples": dict(ai_examples)
    }

    s3.put_object(
        Bucket=BUCKET_NAME,
        Key="analytics/failure-summary.json",
        Body=json.dumps(summary, indent=2),
        ContentType="application/json"
    )

    print("=== FAILURE STATISTICS ===")
    print(json.dumps(summary, indent=2))

    html_dashboard = generate_html_dashboard(summary)

    s3.put_object(
        Bucket=BUCKET_NAME,
        Key="dashboard/index.html",
        Body=html_dashboard,
        ContentType="text/html"
    )

    print("Saved HTML dashboard to S3")

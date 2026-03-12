import os
import time
import json
import boto3
import urllib.request
import urllib.error

s3 = boto3.client("s3")

BUCKET = os.environ["BUCKET_NAME"]
PLOT_API_URL = os.environ["PLOT_API_URL"]
SLEEP_SECONDS = float(os.environ.get("SLEEP_SECONDS", "2.0"))

KEY1 = "assignment1.txt"
KEY2 = "assignment2.txt"
BODY1 = b"Empty Assignment 1"
BODY1_UPDATED = b"Empty Assignment 2222222222"
BODY2 = b"33"


def call_plot_api(url: str):
    request = urllib.request.Request(url=url, method="GET")
    with urllib.request.urlopen(request, timeout=20) as response:
        status = response.status
        body = response.read().decode("utf-8", errors="replace")
        return status, body


def lambda_handler(event, context):
    steps = []

    s3.put_object(Bucket=BUCKET, Key=KEY1, Body=BODY1)
    steps.append({"op": "PUT", "key": KEY1, "bytes": len(BODY1)})
    time.sleep(SLEEP_SECONDS)

    s3.put_object(Bucket=BUCKET, Key=KEY1, Body=BODY1_UPDATED)
    steps.append({"op": "PUT", "key": KEY1, "bytes": len(BODY1_UPDATED)})
    time.sleep(SLEEP_SECONDS)

    s3.delete_object(Bucket=BUCKET, Key=KEY1)
    steps.append({"op": "DELETE", "key": KEY1, "bytes": 0})
    time.sleep(SLEEP_SECONDS)

    s3.put_object(Bucket=BUCKET, Key=KEY2, Body=BODY2)
    steps.append({"op": "PUT", "key": KEY2, "bytes": len(BODY2)})
    time.sleep(SLEEP_SECONDS)

    plot_status = None
    plot_body = None
    plot_error = None

    try:
        plot_status, plot_body = call_plot_api(PLOT_API_URL)
    except urllib.error.HTTPError as exc:
        plot_status = exc.code
        plot_body = exc.read().decode("utf-8", errors="replace")
        plot_error = f"HTTPError: {exc}"
    except Exception as exc:
        plot_error = f"Exception: {exc}"

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(
            {
                "bucket": BUCKET,
                "sleep_seconds": SLEEP_SECONDS,
                "steps": steps,
                "plot_api_url": PLOT_API_URL,
                "plot_status": plot_status,
                "plot_response": plot_body,
                "plot_error": plot_error,
            }
        ),
    }

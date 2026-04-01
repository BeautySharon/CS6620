# import boto3
# import time
# import os
# import urllib.request
# import urllib.error
# import json

# s3 = boto3.client("s3")

# BUCKET_NAME = os.environ["BUCKET_NAME"]
# PLOT_API_URL = os.environ["PLOT_API_URL"]


# def lambda_handler(event, context):
#     steps = []

#     body1 = b"Empty Assignment 1"
#     body2 = b"Empty Assignment 2222222222"
#     body3 = b"33"

#     s3.put_object(Bucket=BUCKET_NAME, Key="assignment1.txt", Body=body1)
#     steps.append({"op": "PUT", "key": "assignment1.txt", "bytes": len(body1)})
#     time.sleep(5)

#     s3.put_object(Bucket=BUCKET_NAME, Key="assignment2.txt", Body=body2)
#     steps.append({"op": "PUT", "key": "assignment2.txt", "bytes": len(body2)})

#     # 给 CloudWatch alarm 充分时间
#     time.sleep(90)

#     s3.put_object(Bucket=BUCKET_NAME, Key="assignment3.txt", Body=body3)
#     steps.append({"op": "PUT", "key": "assignment3.txt", "bytes": len(body3)})

#     # 再给第二次 alarm 时间
#     time.sleep(90)

#     plot_status = None
#     plot_body = None
#     plot_error = None

#     try:
#         with urllib.request.urlopen(PLOT_API_URL, timeout=30) as resp:
#             plot_status = resp.status
#             plot_body = resp.read().decode("utf-8", errors="replace")
#     except urllib.error.HTTPError as e:
#         plot_status = e.code
#         plot_body = e.read().decode("utf-8", errors="replace")
#         plot_error = f"HTTPError: {e}"
#     except Exception as e:
#         plot_error = f"Exception: {e}"

#     return {
#         "statusCode": 200,
#         "body": json.dumps({
#             "bucket": BUCKET_NAME,
#             "steps": steps,
#             "plot_api_url": PLOT_API_URL,
#             "plot_status": plot_status,
#             "plot_body": plot_body,
#             "plot_error": plot_error,
#         })
#     }
import boto3
import time
import os
import urllib.request
import urllib.error
import json
from botocore.exceptions import ClientError

s3 = boto3.client("s3")

BUCKET_NAME = os.environ["BUCKET_NAME"]
PLOT_API_URL = os.environ["PLOT_API_URL"]


def object_exists(bucket: str, key: str) -> bool:
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code in ("404", "NoSuchKey", "NotFound"):
            return False
        raise


def wait_until_deleted(bucket: str, key: str, timeout_seconds: int = 180, poll_interval: int = 5):
    start = time.time()
    while time.time() - start < timeout_seconds:
        if not object_exists(bucket, key):
            return True
        time.sleep(poll_interval)
    return False


def lambda_handler(event, context):
    steps = []

    body1 = b"Empty Assignment 1"              # 18 bytes
    body2 = b"Empty Assignment 2222222222"     # 27 bytes in Python
    body3 = b"33"                              # 2 bytes

    # Step 1
    s3.put_object(Bucket=BUCKET_NAME, Key="assignment1.txt", Body=body1)
    steps.append({"op": "PUT", "key": "assignment1.txt", "bytes": len(body1)})
    time.sleep(3)

    # Step 2
    s3.put_object(Bucket=BUCKET_NAME, Key="assignment2.txt", Body=body2)
    steps.append({"op": "PUT", "key": "assignment2.txt", "bytes": len(body2)})

    # Wait for alarm -> cleaner to delete assignment2.txt
    deleted_assignment2 = wait_until_deleted(BUCKET_NAME, "assignment2.txt", timeout_seconds=180, poll_interval=5)
    steps.append({
        "op": "WAIT_DELETE",
        "key": "assignment2.txt",
        "deleted": deleted_assignment2
    })

    # Step 3
    s3.put_object(Bucket=BUCKET_NAME, Key="assignment3.txt", Body=body3)
    steps.append({"op": "PUT", "key": "assignment3.txt", "bytes": len(body3)})

    # Wait for alarm -> cleaner to delete assignment1.txt
    deleted_assignment1 = wait_until_deleted(BUCKET_NAME, "assignment1.txt", timeout_seconds=180, poll_interval=5)
    steps.append({
        "op": "WAIT_DELETE",
        "key": "assignment1.txt",
        "deleted": deleted_assignment1
    })

    # Give size-tracking lambda a little time to write the final DDB point
    time.sleep(5)

    plot_status = None
    plot_body = None
    plot_error = None

    try:
        with urllib.request.urlopen(PLOT_API_URL, timeout=30) as resp:
            plot_status = resp.status
            plot_body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        plot_status = e.code
        plot_body = e.read().decode("utf-8", errors="replace")
        plot_error = f"HTTPError: {e}"
    except Exception as e:
        plot_error = f"Exception: {e}"

    return {
        "statusCode": 200,
        "body": json.dumps({
            "bucket": BUCKET_NAME,
            "steps": steps,
            "plot_api_url": PLOT_API_URL,
            "plot_status": plot_status,
            "plot_body": plot_body,
            "plot_error": plot_error,
        })
    }
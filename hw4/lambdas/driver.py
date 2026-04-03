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

#     body1 = b"Empty Assignment 1"              # 18 bytes
#     body2 = b"Empty Assignment 2222222222"     # 27 bytes
#     body3 = b"33"                              # 2 bytes

#     # Step 1: put assignment1.txt
#     s3.put_object(Bucket=BUCKET_NAME, Key="assignment1.txt", Body=body1)
#     steps.append({"op": "PUT", "key": "assignment1.txt", "bytes": len(body1)})

#     # Small delay to separate events
#     time.sleep(5)

#     # Step 2: put assignment2.txt
#     s3.put_object(Bucket=BUCKET_NAME, Key="assignment2.txt", Body=body2)
#     steps.append({"op": "PUT", "key": "assignment2.txt", "bytes": len(body2)})

#     # Give CloudWatch/SNS/SQS/Lambda enough time to:
#     # 1) publish logs
#     # 2) update metric
#     # 3) trigger alarm
#     # 4) run cleaner and delete assignment2.txt
#     time.sleep(180)

#     # Step 3: put assignment3.txt
#     s3.put_object(Bucket=BUCKET_NAME, Key="assignment3.txt", Body=body3)
#     steps.append({"op": "PUT", "key": "assignment3.txt", "bytes": len(body3)})
#     time.sleep(20)
#     # Give the second round enough time for:
#     # 1) logging lambda
#     # 2) metric filter
#     # 3) alarm
#     # 4) cleaner to delete assignment1.txt
#     time.sleep(90)

#     # Give size-tracking lambda a little extra time to write the final point
#     time.sleep(15)

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

s3 = boto3.client("s3")

BUCKET_NAME = os.environ["BUCKET_NAME"]
PLOT_API_URL = os.environ["PLOT_API_URL"]


def object_exists(bucket: str, key: str) -> bool:
    paginator = s3.get_paginator("list_objects_v2")

    for page in paginator.paginate(Bucket=bucket):
        for obj in page.get("Contents", []):
            if obj["Key"] == key:
                return True
    return False


def wait_until_deleted(bucket: str, key: str, timeout_seconds: int, interval_seconds: int = 3) -> bool:
    waited = 0

    while waited < timeout_seconds:
        exists = object_exists(bucket, key)
        print(f"waiting for deletion: key={key}, exists={exists}, waited={waited}s")

        if not exists:
            return True

        time.sleep(interval_seconds)
        waited += interval_seconds

    return False


def lambda_handler(event, context):
    steps = []

    body1 = b"Empty Assignment 1"              # 18 bytes
    body2 = b"Empty Assignment 2222222222"     # 27 bytes
    body3 = b"33"                              # 2 bytes

    # Step 1
    s3.put_object(Bucket=BUCKET_NAME, Key="assignment1.txt", Body=body1)
    steps.append({"op": "PUT", "key": "assignment1.txt", "bytes": len(body1)})
    print("uploaded assignment1.txt")

    time.sleep(5)

    # Step 2
    s3.put_object(Bucket=BUCKET_NAME, Key="assignment2.txt", Body=body2)
    steps.append({"op": "PUT", "key": "assignment2.txt", "bytes": len(body2)})
    print("uploaded assignment2.txt")

    # Wait for first cleanup
    deleted_assignment2 = wait_until_deleted(
        BUCKET_NAME,
        "assignment2.txt",
        timeout_seconds=180,
        interval_seconds=3
    )
    steps.append({
        "op": "WAIT_DELETE",
        "key": "assignment2.txt",
        "deleted": deleted_assignment2
    })

    # Buffer for delete-event propagation + size-tracking write
    time.sleep(20)

    # Step 3
    s3.put_object(Bucket=BUCKET_NAME, Key="assignment3.txt", Body=body3)
    steps.append({"op": "PUT", "key": "assignment3.txt", "bytes": len(body3)})
    print("uploaded assignment3.txt")

    # Wait for second cleanup, but do not block forever
    deleted_assignment1 = wait_until_deleted(
        BUCKET_NAME,
        "assignment1.txt",
        timeout_seconds=90,
        interval_seconds=3
    )
    steps.append({
        "op": "WAIT_DELETE",
        "key": "assignment1.txt",
        "deleted": deleted_assignment1
    })

    # Final buffer for size_tracking to write the last point
    time.sleep(15)

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
import json
import os
import boto3

logs = boto3.client("logs")

IGNORE_KEYS = {"plot.png"}
LOG_GROUP_NAME = os.environ["LOG_GROUP_NAME"]


def find_last_created_size(object_name: str) -> int:
    pattern = f'{{ $.object_name = "{object_name}" && $.size_delta = * }}'

    resp = logs.filter_log_events(
        logGroupName=LOG_GROUP_NAME,
        filterPattern=pattern,
        interleaved=True,
    )

    candidates = []
    for event in resp.get("events", []):
        try:
            msg = json.loads(event["message"])
            if msg.get("object_name") == object_name:
                size_delta = int(msg.get("size_delta", 0))
                if size_delta > 0:
                    candidates.append((event["timestamp"], size_delta))
        except Exception:
            continue

    if not candidates:
        return 0

    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def lambda_handler(event, context):
    for record in event["Records"]:
        body = json.loads(record["body"])
        sns_message = json.loads(body["Message"])
        s3_record = sns_message["Records"][0]

        key = s3_record["s3"]["object"]["key"]
        event_name = s3_record["eventName"]

        if key in IGNORE_KEYS:
            print(f"ignoring key: {key}")
            continue

        if "ObjectCreated" in event_name:
            size = int(s3_record["s3"]["object"].get("size", 0))
            delta = size
        elif "ObjectRemoved" in event_name:
            deleted_size = find_last_created_size(key)
            delta = -deleted_size
        else:
            continue

        print(json.dumps({
            "object_name": key,
            "size_delta": delta
        }))

    return {"status": "ok"}
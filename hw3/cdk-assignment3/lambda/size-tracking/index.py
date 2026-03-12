import os
import time
import boto3
from urllib.parse import unquote_plus

TABLE_NAME = os.environ["TABLE_NAME"]
IGNORE_KEYS = {k.strip() for k in os.environ.get("IGNORE_KEYS", "plot").split(",") if k.strip()}

s3 = boto3.client("s3")
ddb = boto3.client("dynamodb")


def compute_bucket_size(bucket: str):
    total = 0
    count = 0
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key in IGNORE_KEYS:
                continue
            total += obj["Size"]
            count += 1
    return total, count


def lambda_handler(event, context):
    records = event.get("Records", [])
    if not records:
        return {"status": "no_records"}

    for record in records:
        raw_key = record.get("s3", {}).get("object", {}).get("key", "")
        key = unquote_plus(raw_key)
        if key in IGNORE_KEYS:
            return {"status": "ignored", "key": key}

    bucket = records[0]["s3"]["bucket"]["name"]
    total_size, object_count = compute_bucket_size(bucket)
    ts_ms = int(time.time() * 1000)

    ddb.put_item(
        TableName=TABLE_NAME,
        Item={
            "bucket": {"S": bucket},
            "ts": {"N": str(ts_ms)},
            "total_size": {"N": str(total_size)},
            "object_count": {"N": str(object_count)},
            "max_key": {"S": "GLOBAL"},
        },
    )

    return {
        "status": "ok",
        "bucket": bucket,
        "ts_ms": ts_ms,
        "total_size": total_size,
        "object_count": object_count,
    }

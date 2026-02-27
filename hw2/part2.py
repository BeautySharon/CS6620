import os
import time
import boto3
from urllib.parse import unquote_plus

# DynamoDB table name
TABLE_NAME = os.environ.get("TABLE_NAME", "S3-object-size-history")

# ignore keys like plot.png so plotting itself doesn't affect size
IGNORE_KEYS = {k.strip() for k in os.environ.get("IGNORE_KEYS", "plot.png").split(",") if k.strip()}

# AWS clients
s3 = boto3.client("s3")
ddb = boto3.client("dynamodb")


def compute_bucket_size(bucket: str):
    # go through all objects in bucket and sum sizes
    total = 0
    count = 0

    # paginator handles buckets with many objects
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket):
        for obj in page.get("Contents", []):
            key = obj["Key"]

            # skip ignored objects
            if key in IGNORE_KEYS:
                continue

            total += obj["Size"]
            count += 1

    return total, count


def lambda_handler(event, context):
    records = event.get("Records", [])
    if not records:
        return {"status": "no_records"}

    # if event is for ignored key, just skip
    for r in records:
        raw_key = r.get("s3", {}).get("object", {}).get("key", "")
        key = unquote_plus(raw_key)
        if key in IGNORE_KEYS:
            return {"status": "ignored", "key": key}

    # assume same bucket for all records
    bucket = records[0]["s3"]["bucket"]["name"]

    # recompute bucket size after this event
    total_size, object_count = compute_bucket_size(bucket)

    # timestamp for time series
    ts_ms = int(time.time() * 1000)

    # write new point to DynamoDB
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
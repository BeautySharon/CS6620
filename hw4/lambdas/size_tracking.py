import json
import time
import os
import boto3

s3 = boto3.client("s3")
ddb = boto3.client("dynamodb")

TABLE_NAME = os.environ["TABLE_NAME"]
IGNORE_KEYS = {"plot.png"}


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
    print("received event:", json.dumps(event))

    for record in event["Records"]:
        body = json.loads(record["body"])          # SQS body
        sns_message = json.loads(body["Message"])  # SNS message
        s3_record = sns_message["Records"][0]      # original S3 event

        bucket = s3_record["s3"]["bucket"]["name"]
        event_key = s3_record["s3"]["object"]["key"]

        if event_key in IGNORE_KEYS:
            print(f"ignoring key: {event_key}")
            continue

        total_size, object_count = compute_bucket_size(bucket)
        ts = int(time.time() * 1000)

        print(
            f"writing to table={TABLE_NAME}, bucket={bucket}, "
            f"total_size={total_size}, object_count={object_count}, ts={ts}"
        )

        ddb.put_item(
            TableName=TABLE_NAME,
            Item={
                "bucket": {"S": bucket},
                "ts": {"N": str(ts)},
                "total_size": {"N": str(total_size)},
                "object_count": {"N": str(object_count)},
                "max_key": {"S": "GLOBAL"},
            },
        )

    return {"status": "ok"}
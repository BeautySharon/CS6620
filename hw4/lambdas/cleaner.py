import boto3
import os

s3 = boto3.client("s3")

BUCKET_NAME = os.environ["BUCKET_NAME"]
IGNORE_KEYS = {"plot.png"}


def lambda_handler(event, context):
    response = s3.list_objects_v2(Bucket=BUCKET_NAME)

    max_obj = None
    max_size = -1

    for obj in response.get("Contents", []):
        key = obj["Key"]
        size = obj["Size"]

        if key in IGNORE_KEYS:
            continue

        if size > max_size:
            max_size = size
            max_obj = key

    if max_obj:
        s3.delete_object(Bucket=BUCKET_NAME, Key=max_obj)
        print(f"Deleted largest object: {max_obj}, size={max_size}")
        return {
            "status": "deleted",
            "key": max_obj,
            "size": max_size
        }

    print("Bucket is empty or only ignored files remain.")
    return {"status": "empty"}
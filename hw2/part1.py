import time
import boto3
from botocore.exceptions import ClientError

REGION = "us-west-2"
BUCKET_NAME = "hw2-sihui-testbucket"
TABLE_NAME = "S3-object-size-history"

s3 = boto3.client("s3", region_name=REGION)
ddb = boto3.client("dynamodb", region_name=REGION)


def create_bucket():
    try:
        if REGION == "us-east-1":
            s3.create_bucket(Bucket=BUCKET_NAME)
        else:
            s3.create_bucket(
                Bucket=BUCKET_NAME,
                CreateBucketConfiguration={"LocationConstraint": REGION},
            )
        print(f"Created bucket: {BUCKET_NAME}")
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
            print(f"[SKIP] Bucket exists: {BUCKET_NAME}")
        else:
            raise


def create_table():
    """
    Table design:
      PK: bucket (S)
      SK: ts (N)  # epoch ms

    GSI:
      IndexName: GSI_GLOBAL_MAX
      PK: max_key (S) always "GLOBAL"
      SK: total_size (N)  # query desc + limit 1 => global max size

    Each record item will include:
      bucket, ts, total_size, object_count, max_key
    """
    try:
        ddb.create_table(
            TableName=TABLE_NAME,
            BillingMode="PAY_PER_REQUEST",
            AttributeDefinitions=[
                {"AttributeName": "bucket", "AttributeType": "S"},
                {"AttributeName": "ts", "AttributeType": "N"},
                {"AttributeName": "max_key", "AttributeType": "S"},
                {"AttributeName": "total_size", "AttributeType": "N"},
            ],
            KeySchema=[
                {"AttributeName": "bucket", "KeyType": "HASH"},
                {"AttributeName": "ts", "KeyType": "RANGE"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "GSI_GLOBAL_MAX",
                    "KeySchema": [
                        {"AttributeName": "max_key", "KeyType": "HASH"},
                        {"AttributeName": "total_size", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
        )
        print(f"Creating table: {TABLE_NAME}")
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "ResourceInUseException":
            print(f"[SKIP] Table exists: {TABLE_NAME}")
        else:
            raise


def wait_for_table_active():
    waiter = ddb.get_waiter("table_exists")
    waiter.wait(TableName=TABLE_NAME)
    while True:
        status = ddb.describe_table(TableName=TABLE_NAME)["Table"]["TableStatus"]
        if status == "ACTIVE":
            break
        time.sleep(2)
    print(f"Table ACTIVE: {TABLE_NAME}")


def main():
    create_bucket()
    create_table()
    wait_for_table_active()
    print("Part 1 complete. Bucket & DDB table should exist and be empty.")


if __name__ == "__main__":
    main()

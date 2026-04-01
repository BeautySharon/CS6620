# import os
# import time
# import json
# import boto3

# import matplotlib
# matplotlib.use("Agg")
# import matplotlib.pyplot as plt

# ddb = boto3.client("dynamodb")
# s3 = boto3.client("s3")

# TABLE_NAME = os.environ["TABLE_NAME"]
# BUCKET_NAME = os.environ["BUCKET_NAME"]
# WINDOW_SECONDS = int(os.environ.get("WINDOW_SECONDS", "120"))


# def query_last_window(bucket_name: str, window_seconds: int):
#     now_ms = int(time.time() * 1000)
#     start_ms = now_ms - window_seconds * 1000

#     resp = ddb.query(
#         TableName=TABLE_NAME,
#         KeyConditionExpression="#b = :b AND #t BETWEEN :s AND :e",
#         ExpressionAttributeNames={
#             "#b": "bucket",
#             "#t": "ts",
#         },
#         ExpressionAttributeValues={
#             ":b": {"S": bucket_name},
#             ":s": {"N": str(start_ms)},
#             ":e": {"N": str(now_ms)},
#         },
#         ScanIndexForward=True
#     )

#     return resp.get("Items", [])


# def query_global_max_size():
#     resp = ddb.query(
#         TableName=TABLE_NAME,
#         IndexName="GSI_GLOBAL_MAX",
#         KeyConditionExpression="#m = :g",
#         ExpressionAttributeNames={
#             "#m": "max_key",
#         },
#         ExpressionAttributeValues={
#             ":g": {"S": "GLOBAL"}
#         },
#         ScanIndexForward=False,
#         Limit=1
#     )

#     items = resp.get("Items", [])
#     if not items:
#         return 0
#     return int(items[0]["total_size"]["N"])


# def lambda_handler(event, context):
#     items = query_last_window(BUCKET_NAME, WINDOW_SECONDS)
#     global_max = query_global_max_size()

#     xs = []
#     ys = []

#     for item in items:
#         xs.append(int(item["ts"]["N"]))
#         ys.append(int(item["total_size"]["N"]))

#     print(f"plotting points count = {len(xs)}, global_max = {global_max}")

#     plt.figure()

#     if xs:
#         t0 = xs[0]
#         xs_rel = [(x - t0) / 1000.0 for x in xs]
#         plt.plot(xs_rel, ys, marker="o")
#         plt.axhline(y=global_max, linestyle="--")
#     else:
#         plt.plot([], [])
#         plt.axhline(y=global_max, linestyle="--")

#     plt.xlabel("time (s)")
#     plt.ylabel("bucket size (bytes)")

#     out_path = "/tmp/plot.png"
#     plt.savefig(out_path)
#     plt.close()

#     s3.upload_file(out_path, BUCKET_NAME, "plot.png")

#     return {
#         "statusCode": 200,
#         "body": json.dumps({
#             "message": "plot created",
#             "bucket": BUCKET_NAME,
#             "points": len(xs),
#             "global_max": global_max,
#             "plot_key": "plot.png"
#         })
#     }
import os
import json
import boto3

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ddb = boto3.client("dynamodb")
s3 = boto3.client("s3")

TABLE_NAME = os.environ["TABLE_NAME"]
BUCKET_NAME = os.environ["BUCKET_NAME"]


def query_all_points(bucket_name: str):
    """
    Query all history points for this bucket, sorted by ts ascending.
    """
    items = []
    last_evaluated_key = None

    while True:
        kwargs = {
            "TableName": TABLE_NAME,
            "KeyConditionExpression": "#b = :b",
            "ExpressionAttributeNames": {
                "#b": "bucket",
            },
            "ExpressionAttributeValues": {
                ":b": {"S": bucket_name},
            },
            "ScanIndexForward": True,
        }

        if last_evaluated_key:
            kwargs["ExclusiveStartKey"] = last_evaluated_key

        resp = ddb.query(**kwargs)
        items.extend(resp.get("Items", []))

        last_evaluated_key = resp.get("LastEvaluatedKey")
        if not last_evaluated_key:
            break

    return items


def query_global_max_size():
    resp = ddb.query(
        TableName=TABLE_NAME,
        IndexName="GSI_GLOBAL_MAX",
        KeyConditionExpression="#m = :g",
        ExpressionAttributeNames={
            "#m": "max_key",
        },
        ExpressionAttributeValues={
            ":g": {"S": "GLOBAL"}
        },
        ScanIndexForward=False,
        Limit=1
    )

    items = resp.get("Items", [])
    if not items:
        return 0
    return int(items[0]["total_size"]["N"])


def lambda_handler(event, context):
    items = query_all_points(BUCKET_NAME)
    global_max = query_global_max_size()

    xs = []
    ys = []

    for item in items:
        xs.append(int(item["ts"]["N"]))
        ys.append(int(item["total_size"]["N"]))

    print(f"points={len(xs)}, global_max={global_max}")

    plt.figure()

    if xs:
        t0 = xs[0]
        xs_rel = [(x - t0) / 1000.0 for x in xs]
        plt.plot(xs_rel, ys, marker="o")
    else:
        plt.plot([], [])

    plt.axhline(y=global_max, linestyle="--")
    plt.xlabel("time (s)")
    plt.ylabel("bucket size (bytes)")

    out_path = "/tmp/plot.png"
    plt.savefig(out_path)
    plt.close()

    s3.upload_file(out_path, BUCKET_NAME, "plot.png")

    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "plot created",
            "bucket": BUCKET_NAME,
            "points": len(xs),
            "global_max": global_max,
            "plot_key": "plot.png"
        })
    }
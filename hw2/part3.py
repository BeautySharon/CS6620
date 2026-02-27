import os
import time
import boto3

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# config
TABLE_NAME = os.environ.get("TABLE_NAME", "S3-object-size-history")
BUCKET_NAME = os.environ["BUCKET_NAME"]
PLOT_KEY = os.environ.get("PLOT_KEY", "plot.png")
WINDOW_SECONDS = int(os.environ.get("WINDOW_SECONDS", "10"))

# AWS clients
ddb = boto3.client("dynamodb")
s3 = boto3.client("s3")


def query_last_window(bucket: str, window_seconds: int):
    # get recent size history points from DynamoDB
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - window_seconds * 1000

    resp = ddb.query(
        TableName=TABLE_NAME,
        KeyConditionExpression="#b = :b AND #t BETWEEN :s AND :e",
        ExpressionAttributeNames={
            "#b": "bucket",
            "#t": "ts",
        },
        ExpressionAttributeValues={
            ":b": {"S": bucket},
            ":s": {"N": str(start_ms)},
            ":e": {"N": str(now_ms)},
        },
        ScanIndexForward=True,  # time ascending
    )

    items = resp.get("Items", [])
    points = [(int(it["ts"]["N"]), int(it["total_size"]["N"])) for it in items]
    return points


def query_global_max_size():
    # get max bucket size ever recorded (using GSI)
    resp = ddb.query(
        TableName=TABLE_NAME,
        IndexName="GSI_GLOBAL_MAX",
        KeyConditionExpression="max_key = :g",
        ExpressionAttributeValues={
            ":g": {"S": "GLOBAL"}
        },
        ScanIndexForward=False,  # biggest total_size first
        Limit=1
    )
    items = resp.get("Items", [])
    if not items:
        return 0
    return int(items[0]["total_size"]["N"])


def make_plot(points, global_max):
    # create plot in Lambda tmp folder
    out_path = "/tmp/plot.png"

    plt.figure()

    if points:
        # convert timestamps to seconds relative to first point
        t0 = points[0][0]
        xs = [(t - t0) / 1000.0 for t, _ in points]  # seconds
        ys = [size for _, size in points]

        plt.plot(xs, ys, marker="o")
        plt.axhline(y=global_max)
        plt.xlabel("time (s)")
        plt.ylabel("bucket size (bytes)")
    else:
        # no data case
        plt.title("No data in last window")
        plt.axhline(y=global_max)
        plt.xlabel("time (s)")
        plt.ylabel("bucket size (bytes)")

    plt.savefig(out_path)
    plt.close()
    return out_path


def lambda_handler(event, context):
    # 1) query last 10 seconds for TestBucket
    points = query_last_window(BUCKET_NAME, WINDOW_SECONDS)

    # 2) query global max across all buckets (all time)
    global_max = query_global_max_size()

    # 3) plot and upload to S3
    plot_path = make_plot(points, global_max)
    s3.upload_file(plot_path, BUCKET_NAME, PLOT_KEY)

    # 4) return response for API Gateway (synchronous)
    body = {
        "bucket": BUCKET_NAME,
        "plot_key": PLOT_KEY,
        "points": len(points),
        "global_max": global_max,
        "window_seconds": WINDOW_SECONDS,
    }

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": str(body)
    }

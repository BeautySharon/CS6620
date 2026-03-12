import os
import json
import time
import boto3

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

TABLE_NAME = os.environ["TABLE_NAME"]
BUCKET_NAME = os.environ["BUCKET_NAME"]
PLOT_KEY = os.environ.get("PLOT_KEY", "plot")
WINDOW_SECONDS = int(os.environ.get("WINDOW_SECONDS", "10"))

ddb = boto3.client("dynamodb")
s3 = boto3.client("s3")


def query_last_window(bucket: str, window_seconds: int):
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - window_seconds * 1000

    response = ddb.query(
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
        ScanIndexForward=True,
    )

    items = response.get("Items", [])
    return [(int(item["ts"]["N"]), int(item["total_size"]["N"])) for item in items]


def query_global_max_size():
    response = ddb.query(
        TableName=TABLE_NAME,
        IndexName="GSI_GLOBAL_MAX",
        KeyConditionExpression="max_key = :g",
        ExpressionAttributeValues={":g": {"S": "GLOBAL"}},
        ScanIndexForward=False,
        Limit=1,
    )
    items = response.get("Items", [])
    if not items:
        return 0
    return int(items[0]["total_size"]["N"])


def make_plot(points, global_max):
    output_path = "/tmp/plot.png"
    plt.figure()

    if points:
        t0 = points[0][0]
        xs = [(timestamp - t0) / 1000.0 for timestamp, _ in points]
        ys = [size for _, size in points]
        plt.plot(xs, ys, marker="o")
        plt.axhline(y=global_max, linestyle="--")
        plt.xlabel("time (s)")
        plt.ylabel("bucket size (bytes)")
        plt.title(f"Bucket size for {BUCKET_NAME} in last {WINDOW_SECONDS}s")
    else:
        plt.axhline(y=global_max, linestyle="--")
        plt.xlabel("time (s)")
        plt.ylabel("bucket size (bytes)")
        plt.title(f"No data for {BUCKET_NAME} in last {WINDOW_SECONDS}s")

    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()
    return output_path


def lambda_handler(event, context):
    points = query_last_window(BUCKET_NAME, WINDOW_SECONDS)
    global_max = query_global_max_size()
    plot_path = make_plot(points, global_max)
    s3.upload_file(plot_path, BUCKET_NAME, PLOT_KEY)

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
        "body": json.dumps(body),
    }

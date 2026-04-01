import json

IGNORE_KEYS = {"plot.png"}


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
            delta = 0
        else:
            continue

        print(json.dumps({
            "object_name": key,
            "size_delta": delta
        }))

    return {"status": "ok"}
# HW4 Final CDK Version

This project creates the entire Assignment 4 architecture with AWS CDK.

## Resources created
- S3 bucket (`TestBucket`)
- DynamoDB table (`S3-object-size-history`)
- SNS topic for S3 event fan-out
- Two SQS queues
- Size-tracking Lambda
- Logging Lambda
- Cleaner Lambda
- Plotting Lambda
- Driver Lambda
- API Gateway endpoint for the plotting Lambda
- CloudWatch metric filter (`Assignment4App / TotalObjectSize`)
- CloudWatch alarm that invokes the Cleaner Lambda when metric SUM > 20

## Deploy
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cdk bootstrap
cdk deploy
```

## Test
1. Deploy the stack.
2. Copy the stack outputs: bucket name, plot API URL, and driver function name.
3. Invoke the driver Lambda from the AWS Console or CLI.
4. Verify:
   - `assignment1.txt` is created.
   - `assignment2.txt` is created.
   - Alarm fires and Cleaner deletes the largest object.
   - `assignment3.txt` is created.
   - Plotting API is called.
   - `plot.png` appears in the bucket.
5. Check CloudWatch Logs for the JSON log lines from `LoggingLambda`.
6. Check CloudWatch Metrics for `Assignment4App / TotalObjectSize`.
7. Check the DynamoDB table for time-series entries.

## Notes
- Delete events do not include object size. `LoggingLambda` looks up the most recent positive creation/update size from its own log group using `filter_log_events`.
- `plot.png` is ignored by the size-tracking, logging, and cleaner logic so plotting does not interfere with the bucket-size history.

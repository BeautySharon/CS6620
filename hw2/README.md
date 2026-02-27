# CS6650 HW2 – Use Lambda to Count Total Object Size

# Part 1 – Infrastructure Setup (Local Python Program)

A local Python script was implemented to create the required AWS resources:

- The S3 bucket (`TestBucket`)
- The DynamoDB table (`S3-object-size-history`)

<img src="screenshot/bucket_create.png" width="700">
<img src="screenshot/dynamo.png" width="700">

## DynamoDB Schema Design

Primary key:

- **PK:** `bucket` (string)
- **SK:** `ts` (timestamp in epoch ms)

Attributes:

- `total_size`
- `object_count`
- `max_key` (constant value `"GLOBAL"` for GSI usage)

## Global Secondary Index

To support efficient retrieval of the global maximum bucket size:

- **GSI name:** `GSI_GLOBAL_MAX`
- **PK:** `max_key`
- **SK:** `total_size`

---

# Part 2 – Size-Tracking Lambda

## Edit Code

<img src="screenshot/part2.png" width="700">

## Add Trigger

<img src="screenshot/add_trigger.png" width="700">

The Lambda function is triggered by S3 events:

- ObjectCreated
- ObjectRemoved

## DynamoDB Test Example

1. Upload a `test.txt` file to S3

<img src="screenshot/part2_test_1.png" width="700">

2. The DynamoDB table shows the updated record

<img src="screenshot/part2_test_2.png" width="700">

---

# Part 3 – Plotting Lambda

## Edit Code

<img src="screenshot/part3.png" width="700">

## Add Plot Layer

A plotting dependency layer was attached to support visualization generation.

## Test

1. Invoke the API URL

   https://4u3fbx893b.execute-api.us-west-2.amazonaws.com/prod/plot

<img src="screenshot/part3_test_1.png" width="700">

2. A plot file is uploaded to S3

<img src="screenshot/part3_test_2.png" width="700">

3. Generated plot file

<img src="screenshot/part3_test_plot.png" width="700">

---

# Part 4 – Driver Lambda

## Edit Code

<img src="screenshot/part4.png" width="700">

## Test

<img src="screenshot/part4_test1.png" width="700">
<img src="screenshot/part4_test2.png" width="700">
<img src="screenshot/part4_test3.png" width="700">
<img src="screenshot/part4_plot.png" width="700">

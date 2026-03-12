# Assignment 3 CDK Project

This CDK project deploys the same resources required by Assignment 2, but using AWS CDK in TypeScript:

- 3 Lambda functions
  - `size-tracking`
  - `plotting`
  - `driver`
- 1 S3 bucket
- 1 DynamoDB table with a GSI named `GSI_GLOBAL_MAX`
- 1 REST API with `GET /plot`
- S3 event notifications from the bucket to the size-tracking Lambda

## Stack design

The app is split into **three stacks** instead of one large stack:

1. **Assignment3DataStack**
   - S3 bucket
   - DynamoDB table
   - GSI

2. **Assignment3ServiceStack**
   - size-tracking Lambda
   - plotting Lambda
   - S3 event notifications to size-tracking Lambda
   - permissions for Lambda ↔ S3/DynamoDB

3. **Assignment3ApiDriverStack**
   - API Gateway REST API
   - `GET /plot`
   - driver Lambda
   - driver Lambda environment variable for the API URL

## Folder structure

```text
cdk-assignment3/
├── bin/
│   └── assignment3.ts
├── lib/
│   ├── api-driver-stack.ts
│   ├── data-stack.ts
│   └── service-stack.ts
├── lambda/
│   ├── driver/
│   │   ├── index.py
│   │   └── requirements.txt
│   ├── plotting/
│   │   ├── index.py
│   │   └── requirements.txt
│   └── size-tracking/
│       ├── index.py
│       └── requirements.txt
├── cdk.json
├── package.json
├── tsconfig.json
└── README.md
```

## How to deploy

### 1. Install dependencies

```bash
npm install
```

### 2. Bootstrap CDK (first time only per account/region)

```bash
npx cdk bootstrap
```

### 3. Synthesize

```bash
npx cdk synth
```

### 4. Deploy

```bash
npx cdk deploy --all
```

## How to test

After deploy:

1. Go to **Lambda** in the AWS Console.
2. Find the driver Lambda from the stack output.
3. Invoke it manually.
4. The driver Lambda will:
   - create `assignment1.txt`
   - update `assignment1.txt`
   - delete `assignment1.txt`
   - create `assignment2.txt`
   - call `GET /plot`
5. Download the `plot` object from the S3 bucket.

## Notes

- Resource names are **not hardcoded**. CDK generates the physical names automatically.
- The plotting Lambda uses DynamoDB **query**, not scan.
- The GSI is used to retrieve the all-time global maximum bucket size.
- The plot object is stored using key `plot` to match the assignment wording.
- The plotting artifact is excluded from bucket-size tracking using `IGNORE_KEYS=plot`.

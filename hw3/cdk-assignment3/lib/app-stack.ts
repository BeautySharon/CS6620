import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as apigateway from "aws-cdk-lib/aws-apigateway";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as s3n from "aws-cdk-lib/aws-s3-notifications";
import { PythonFunction } from "@aws-cdk/aws-lambda-python-alpha";

export interface AppStackProps extends cdk.StackProps {
  historyTable: dynamodb.ITable;
}

export class AppStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: AppStackProps) {
    super(scope, id, props);

    const bucket = new s3.Bucket(this, "TestBucket", {
      autoDeleteObjects: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    const sizeTrackingLambda = new PythonFunction(this, "SizeTrackingLambda", {
      entry: "lambda/size-tracking",
      index: "index.py",
      handler: "lambda_handler",
      runtime: lambda.Runtime.PYTHON_3_11,
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
      environment: {
        TABLE_NAME: props.historyTable.tableName,
        IGNORE_KEYS: "plot",
      },
    });

    const plottingLambda = new PythonFunction(this, "PlottingLambda", {
      entry: "lambda/plotting",
      index: "index.py",
      handler: "lambda_handler",
      runtime: lambda.Runtime.PYTHON_3_11,
      timeout: cdk.Duration.seconds(60),
      memorySize: 1024,
      environment: {
        TABLE_NAME: props.historyTable.tableName,
        BUCKET_NAME: bucket.bucketName,
        PLOT_KEY: "plot",
        WINDOW_SECONDS: "10",
      },
    });

    const api = new apigateway.RestApi(this, "PlotApi", {
      deployOptions: { stageName: "prod" },
    });

    const plotResource = api.root.addResource("plot");
    plotResource.addMethod(
      "GET",
      new apigateway.LambdaIntegration(plottingLambda),
    );

    const driverLambda = new PythonFunction(this, "DriverLambda", {
      entry: "lambda/driver",
      index: "index.py",
      handler: "lambda_handler",
      runtime: lambda.Runtime.PYTHON_3_11,
      timeout: cdk.Duration.seconds(60),
      memorySize: 256,
      environment: {
        BUCKET_NAME: bucket.bucketName,
        PLOT_API_URL: `${api.url}plot`,
        SLEEP_SECONDS: "2.0",
      },
    });

    props.historyTable.grantReadWriteData(sizeTrackingLambda);
    props.historyTable.grantReadData(plottingLambda);
    props.historyTable.grantReadWriteData(driverLambda);

    bucket.grantRead(sizeTrackingLambda);
    bucket.grantReadWrite(plottingLambda);
    bucket.grantReadWrite(driverLambda);

    bucket.addEventNotification(
      s3.EventType.OBJECT_CREATED,
      new s3n.LambdaDestination(sizeTrackingLambda),
    );

    bucket.addEventNotification(
      s3.EventType.OBJECT_REMOVED,
      new s3n.LambdaDestination(sizeTrackingLambda),
    );

    new cdk.CfnOutput(this, "BucketName", {
      value: bucket.bucketName,
    });

    new cdk.CfnOutput(this, "PlotApiUrl", {
      value: `${api.url}plot`,
    });

    new cdk.CfnOutput(this, "DriverLambdaName", {
      value: driverLambda.functionName,
    });
  }
}

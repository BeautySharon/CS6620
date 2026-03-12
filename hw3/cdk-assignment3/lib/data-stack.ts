import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";

export class DataStack extends cdk.Stack {
  public readonly historyTable: dynamodb.Table;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    this.historyTable = new dynamodb.Table(this, "S3ObjectSizeHistoryTable", {
      partitionKey: { name: "bucket", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "ts", type: dynamodb.AttributeType.NUMBER },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    this.historyTable.addGlobalSecondaryIndex({
      indexName: "GSI_GLOBAL_MAX",
      partitionKey: { name: "max_key", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "total_size", type: dynamodb.AttributeType.NUMBER },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    new cdk.CfnOutput(this, "TableName", {
      value: this.historyTable.tableName,
    });
  }
}

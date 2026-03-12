#!/usr/bin/env node
import * as cdk from "aws-cdk-lib";
import { DataStack } from "../lib/data-stack";
import { AppStack } from "../lib/app-stack";

const app = new cdk.App();

const env = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION,
};

const dataStack = new DataStack(app, "Assignment3DataStack", { env });

const appStack = new AppStack(app, "Assignment3AppStack", {
  env,
  historyTable: dataStack.historyTable,
});

appStack.addDependency(dataStack);

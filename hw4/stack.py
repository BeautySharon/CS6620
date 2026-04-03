from aws_cdk import *
from constructs import Construct
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sqs as sqs
from aws_cdk import aws_sns_subscriptions as subs
from aws_cdk import aws_lambda_event_sources as sources
from aws_cdk import aws_dynamodb as ddb
from aws_cdk import aws_s3_notifications as s3n
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_cloudwatch as cw
from aws_cdk import aws_cloudwatch_actions as actions
from aws_cdk import aws_logs as logs
from aws_cdk import aws_iam as iam


class Hw4Stack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # ---------------------------
        # S3 bucket
        # ---------------------------
        bucket = s3.Bucket(
            self,
            "TestBucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # ---------------------------
        # DynamoDB table
        # ---------------------------
        table = ddb.Table(
            self,
            "Table",
            partition_key=ddb.Attribute(name="bucket", type=ddb.AttributeType.STRING),
            sort_key=ddb.Attribute(name="ts", type=ddb.AttributeType.NUMBER),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        table.add_global_secondary_index(
            index_name="GSI_GLOBAL_MAX",
            partition_key=ddb.Attribute(name="max_key", type=ddb.AttributeType.STRING),
            sort_key=ddb.Attribute(name="total_size", type=ddb.AttributeType.NUMBER),
            projection_type=ddb.ProjectionType.ALL,
        )

        # ---------------------------
        # SNS + SQS fanout
        # ---------------------------
        topic = sns.Topic(self, "Topic")

        size_queue = sqs.Queue(self, "SizeQueue")
        log_queue = sqs.Queue(self, "LogQueue")

        topic.add_subscription(subs.SqsSubscription(size_queue))
        topic.add_subscription(subs.SqsSubscription(log_queue))

        bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.SnsDestination(topic)
        )

        bucket.add_event_notification(
            s3.EventType.OBJECT_REMOVED,
            s3n.SnsDestination(topic)
        )

        # ---------------------------
        # Size-tracking lambda
        # ---------------------------
        size_lambda = _lambda.Function(
            self,
            "SizeLambda",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="size_tracking.lambda_handler",
            code=_lambda.Code.from_asset("lambdas"),
            timeout=Duration.seconds(30),
            environment={
                "TABLE_NAME": table.table_name
            }
        )

        size_lambda.add_event_source(sources.SqsEventSource(size_queue))
        table.grant_write_data(size_lambda)
        bucket.grant_read(size_lambda)

        # ---------------------------
        # Logging lambda
        # ---------------------------
        # Use a fixed function name to avoid circular dependency.
        logging_lambda_name = "hw4-logging-lambda"
        logging_log_group_name = f"/aws/lambda/{logging_lambda_name}"

        logging_lambda = _lambda.Function(
            self,
            "LoggingLambda",
            function_name=logging_lambda_name,
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="logging_lambda.lambda_handler",
            code=_lambda.Code.from_asset("lambdas"),
            timeout=Duration.seconds(30),
            environment={
                "LOG_GROUP_NAME": logging_log_group_name
            }
        )

        logging_lambda.add_event_source(sources.SqsEventSource(log_queue))

        # Allow the logging lambda to search CloudWatch logs.
        logging_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["logs:FilterLogEvents"],
                resources=["*"],
            )
        )

        # Explicitly create the log group so that MetricFilter can attach to it.
        logging_log_group = logs.LogGroup(
            self,
            "LoggingLambdaLogGroup",
            log_group_name=logging_log_group_name,
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # ---------------------------
        # Metric filter
        # ---------------------------
        metric_filter = logs.MetricFilter(
            self,
            "LoggingMetricFilter",
            log_group=logging_log_group,
            filter_pattern=logs.FilterPattern.literal('{ $.size_delta = * }'),
            metric_namespace="Assignment4App",
            metric_name="TotalObjectSize",
            metric_value="$.size_delta",
        )

        # Make sure metric filter is created after the log group.
        metric_filter.node.add_dependency(logging_log_group)

        # ---------------------------
        # Cleaner lambda
        # ---------------------------
        cleaner = _lambda.Function(
            self,
            "Cleaner",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="cleaner.lambda_handler",
            code=_lambda.Code.from_asset("lambdas"),
            timeout=Duration.seconds(30),
            environment={
                "BUCKET_NAME": bucket.bucket_name
            }
        )

        bucket.grant_read_write(cleaner)

        # ---------------------------
        # Plotting lambda
        # ---------------------------
        layer = _lambda.LayerVersion(
            self,
            "MatplotlibLayer",
            code=_lambda.Code.from_asset("matplotlib-layer"),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_11],
        )

        plotting_lambda = _lambda.Function(
            self,
            "PlottingLambda",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="plotting.lambda_handler",
            code=_lambda.Code.from_asset("lambdas"),
            layers=[layer],
            memory_size=512,
            timeout=Duration.seconds(30),
            environment={
                "TABLE_NAME": table.table_name,
                "BUCKET_NAME": bucket.bucket_name,
                "MPLCONFIGDIR": "/tmp/matplotlib",
                "WINDOW_SECONDS": "120"
            }
        )

        table.grant_read_data(plotting_lambda)
        bucket.grant_read_write(plotting_lambda)

        api = apigw.LambdaRestApi(
            self,
            "PlotAPI",
            handler=plotting_lambda
        )

        # ---------------------------
        # Driver lambda
        # ---------------------------
        driver = _lambda.Function(
            self,
            "DriverLambda",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="driver.lambda_handler",
            code=_lambda.Code.from_asset("lambdas"),
            timeout=Duration.seconds(600),
            environment={
                "BUCKET_NAME": bucket.bucket_name,
                "PLOT_API_URL": api.url
            }
        )

        bucket.grant_read_write(driver)

        # ---------------------------
        # CloudWatch metric + alarm
        # ---------------------------
        metric = cw.Metric(
            namespace="Assignment4App",
            metric_name="TotalObjectSize",
            statistic="Sum",
            period=Duration.minutes(2)
        )

        alarm = cw.Alarm(
            self,
            "Alarm",
            metric=metric,
            threshold=20,
            evaluation_periods=1,
            datapoints_to_alarm=1,
            comparison_operator=cw.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            treat_missing_data=cw.TreatMissingData.NOT_BREACHING,
        )

        alarm.add_alarm_action(actions.LambdaAction(cleaner))

        # ---------------------------
        # Outputs
        # ---------------------------
        CfnOutput(self, "BucketName", value=bucket.bucket_name)
        CfnOutput(self, "TableName", value=table.table_name)
        CfnOutput(self, "PlotApiUrl", value=api.url)
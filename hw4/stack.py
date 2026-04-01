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


class Hw4Stack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        bucket = s3.Bucket(
            self,
            "TestBucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

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

        size_lambda = _lambda.Function(
            self,
            "SizeLambda",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="size_tracking.lambda_handler",
            code=_lambda.Code.from_asset("lambdas"),
            timeout=Duration.seconds(30),
            environment={"TABLE_NAME": table.table_name}
        )
        size_lambda.add_event_source(sources.SqsEventSource(size_queue))
        table.grant_write_data(size_lambda)
        bucket.grant_read(size_lambda)

        logging_lambda = _lambda.Function(
            self,
            "LoggingLambda",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="logging_lambda.lambda_handler",
            code=_lambda.Code.from_asset("lambdas"),
            timeout=Duration.seconds(30),
        )
        logging_lambda.add_event_source(sources.SqsEventSource(log_queue))

        logging_log_group = logs.LogGroup(
            self,
            "LoggingLambdaLogGroup",
            log_group_name=f"/aws/lambda/{logging_lambda.function_name}",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )

        metric_filter = logs.MetricFilter(
            self,
            "LoggingMetricFilter",
            log_group=logging_log_group,
            filter_pattern=logs.FilterPattern.literal('{ $.size_delta = * }'),
            metric_namespace="Assignment4App",
            metric_name="TotalObjectSize",
            metric_value="$.size_delta",
        )
        metric_filter.node.add_dependency(logging_log_group)

        cleaner = _lambda.Function(
            self,
            "Cleaner",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="cleaner.lambda_handler",
            code=_lambda.Code.from_asset("lambdas"),
            timeout=Duration.seconds(30),
            environment={"BUCKET_NAME": bucket.bucket_name}
        )
        bucket.grant_read_write(cleaner)

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

        driver = _lambda.Function(
            self,
            "DriverLambda",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="driver.lambda_handler",
            code=_lambda.Code.from_asset("lambdas"),
            timeout=Duration.seconds(300),
            environment={
                "BUCKET_NAME": bucket.bucket_name,
                "PLOT_API_URL": api.url
            }
        )
        bucket.grant_read_write(driver)

        metric = cw.Metric(
            namespace="Assignment4App",
            metric_name="TotalObjectSize",
            statistic="Sum",
            period=Duration.minutes(1)
        )

        alarm = cw.Alarm(
            self,
            "Alarm",
            metric=metric,
            threshold=20,
            evaluation_periods=1,
            datapoints_to_alarm=1,
            comparison_operator=cw.ComparisonOperator.GREATER_THAN_THRESHOLD,
        )
        alarm.add_alarm_action(actions.LambdaAction(cleaner))

        CfnOutput(self, "BucketName", value=bucket.bucket_name)
        CfnOutput(self, "TableName", value=table.table_name)
        CfnOutput(self, "PlotApiUrl", value=api.url)
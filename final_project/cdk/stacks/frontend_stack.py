import os
from aws_cdk import (
    Stack, RemovalPolicy, CfnOutput,
    aws_s3 as s3,
    aws_s3_deployment as s3_deploy,
)
from constructs import Construct

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")


class FrontendStack(Stack):
    """
    Hosts the React (Vite) build as an S3 static website.
    Independent of the other stacks – can be deployed separately.

    Deploy steps:
        cd frontend && npm run build
        cdk deploy FrontendStack

    Outputs (CloudFormation):
        FrontendUrl – public S3 website URL
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        bucket = s3.Bucket(
            self, "FrontendBucket",
            website_index_document="index.html",
            website_error_document="index.html",   # React router handles 404s
            public_read_access=True,
            block_public_access=s3.BlockPublicAccess(
                block_public_acls=False,
                block_public_policy=False,
                ignore_public_acls=False,
                restrict_public_buckets=False,
            ),
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # Only deploy if the React build exists (frontend/dist/)
        dist_dir = os.path.join(ROOT, "frontend", "dist")
        if os.path.isdir(dist_dir):
            s3_deploy.BucketDeployment(
                self, "Deploy",
                sources=[s3_deploy.Source.asset(dist_dir)],
                destination_bucket=bucket,
            )

        CfnOutput(
            self, "FrontendUrl",
            value=bucket.bucket_website_url,
            description="S3 static website URL",
        )

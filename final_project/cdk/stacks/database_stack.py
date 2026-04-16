from aws_cdk import (
    Stack, Duration, RemovalPolicy,
    aws_ec2 as ec2,
    aws_rds as rds,
    aws_elasticache as elasticache,
)
from constructs import Construct

from .network_stack import NetworkStack


class DatabaseStack(Stack):
    """
    Provisions RDS PostgreSQL and ElastiCache Redis.
    Depends on NetworkStack for VPC and security groups.

    Outputs (as Python attributes):
        database      – RDS DatabaseInstance
        db_secret     – Secrets Manager secret with DB credentials
        redis_cluster – ElastiCache CfnCacheCluster
        redis_addr    – "<host>:6379" string for env-var injection
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        network: NetworkStack,
        **kwargs,
    ):
        super().__init__(scope, construct_id, **kwargs)

        # ── RDS PostgreSQL 16 ─────────────────────────────────────────────────
        self.database = rds.DatabaseInstance(
            self, "Postgres",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_16,
            ),
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.T3, ec2.InstanceSize.MICRO,
            ),
            credentials=rds.Credentials.from_generated_secret("twitter"),
            database_name="twitter",
            vpc=network.vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            security_groups=[network.db_sg],
            removal_policy=RemovalPolicy.DESTROY,
            deletion_protection=False,
            backup_retention=Duration.days(0),   # no automated backups for demo
        )

        # Expose the auto-generated Secrets Manager secret for the containers
        self.db_secret = self.database.secret

        # ── ElastiCache Redis 7 ───────────────────────────────────────────────
        redis_subnet_group = elasticache.CfnSubnetGroup(
            self, "RedisSubnetGroup",
            subnet_ids=[sn.subnet_id for sn in network.vpc.private_subnets],
            description="Mini-Twitter Redis subnet group",
        )

        self.redis_cluster = elasticache.CfnCacheCluster(
            self, "Redis",
            cache_node_type="cache.t3.micro",
            engine="redis",
            num_cache_nodes=1,
            cache_subnet_group_name=redis_subnet_group.ref,
            vpc_security_group_ids=[network.redis_sg.security_group_id],
        )

        # Convenience string used as REDIS_ADDR env var in ECS tasks
        self.redis_addr = (
            f"{self.redis_cluster.attr_redis_endpoint_address}:6379"
        )

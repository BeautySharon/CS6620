from aws_cdk import Stack, aws_ec2 as ec2
from constructs import Construct


class NetworkStack(Stack):
    """
    Provisions the VPC and all security groups.
    Other stacks import these as constructor arguments.

    Outputs (as Python attributes):
        vpc       – the VPC
        db_sg     – security group for RDS Postgres (allows inbound 5432 from ECS)
        redis_sg  – security group for ElastiCache Redis (allows inbound 6379 from ECS)
        ecs_sg    – security group attached to every ECS Fargate task
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # ── VPC: 2 AZs, public + private subnets, 1 NAT gateway ──────────────
        self.vpc = ec2.Vpc(
            self, "Vpc",
            max_azs=2,
            nat_gateways=1,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24,
                ),
            ],
        )

        # ── Security groups ───────────────────────────────────────────────────
        # NOTE: ecs_sg is intentionally NOT created here.
        # It lives in ContainerStack alongside the ALB so CDK can wire
        # ALB → ECS ingress rules within a single stack (no cyclic cross-stack refs).

        # RDS: allow Postgres from anywhere in the VPC
        self.db_sg = ec2.SecurityGroup(
            self, "DbSg",
            vpc=self.vpc,
            description="RDS Postgres - allow VPC inbound",
        )
        self.db_sg.add_ingress_rule(
            ec2.Peer.ipv4(self.vpc.vpc_cidr_block),
            ec2.Port.tcp(5432),
            "VPC to Postgres",
        )

        # Redis: allow Redis from anywhere in the VPC
        self.redis_sg = ec2.SecurityGroup(
            self, "RedisSg",
            vpc=self.vpc,
            description="ElastiCache Redis - allow VPC inbound",
        )
        self.redis_sg.add_ingress_rule(
            ec2.Peer.ipv4(self.vpc.vpc_cidr_block),
            ec2.Port.tcp(6379),
            "VPC to Redis",
        )

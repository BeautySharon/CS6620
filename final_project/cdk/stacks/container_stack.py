import os
from aws_cdk import (
    Duration, Stack, RemovalPolicy, CfnOutput,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecr_assets as ecr_assets,
    aws_logs as logs,
    aws_elasticloadbalancingv2 as elbv2,
    aws_servicediscovery as sd,
)
from constructs import Construct

from .network_stack import NetworkStack
from .database_stack import DatabaseStack

# Absolute path to the repo root (two levels up from cdk/stacks/)
ROOT = os.path.join(os.path.dirname(__file__), "..", "..")


class ContainerStack(Stack):
    """
    Provisions the ECS Fargate cluster, Application Load Balancer,
    and all 4 microservice tasks (Gateway, User, Tweet, Timeline).
    Depends on NetworkStack and DatabaseStack.

    Outputs (CloudFormation):
        AlbDnsName – public DNS of the load balancer
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        network: NetworkStack,
        database: DatabaseStack,
        **kwargs,
    ):
        super().__init__(scope, construct_id, **kwargs)

        jwt_secret = "supersecretjwtkey"  # swap for SecretsManager in production

        # ── ECS security group (lives here alongside the ALB to avoid cyclic refs) ─
        ecs_sg = ec2.SecurityGroup(
            self, "EcsSg",
            vpc=network.vpc,
            description="ECS Fargate tasks",
            allow_all_outbound=True,
        )
        # Allow all inbound from within the VPC:
        #   - ALB health-check probes
        #   - Inter-service calls via Cloud Map (e.g. gateway → user-service)
        ecs_sg.add_ingress_rule(
            ec2.Peer.ipv4(network.vpc.vpc_cidr_block),
            ec2.Port.all_traffic(),
            "Allow all VPC traffic into ECS tasks",
        )

        # ── Cloud Map private DNS namespace (mini-twitter.local) ─────────────
        namespace = sd.PrivateDnsNamespace(
            self, "Namespace",
            name="mini-twitter.local",
            vpc=network.vpc,
        )

        # ── ECS cluster + CloudWatch log group ────────────────────────────────
        cluster = ecs.Cluster(self, "Cluster", vpc=network.vpc)

        log_group = logs.LogGroup(
            self, "LogGroup",
            log_group_name="/mini-twitter/ecs",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # ── Application Load Balancer ─────────────────────────────────────────
        alb = elbv2.ApplicationLoadBalancer(
            self, "Alb",
            vpc=network.vpc,
            internet_facing=True,
        )
        listener = alb.add_listener("Listener", port=80, open=True)

        # Default response for unmatched paths
        listener.add_action(
            "Default",
            action=elbv2.ListenerAction.fixed_response(
                404,
                content_type="application/json",
                message_body='{"error":"not found"}',
            ),
        )

        # ── Helper: build one Fargate service and attach it to the ALB ────────
        def _register_service(
            name: str,
            port: int,
            image_subdir: str,
            env: dict,
            alb_priority: int,
            path_patterns: list[str],
            needs_db: bool = False,
        ):
            task = ecs.FargateTaskDefinition(
                self, f"{name}Task",
                cpu=256,
                memory_limit_mib=512,
            )

            # Inject DB password from Secrets Manager as DB_PASSWORD;
            # services assemble the full URL from DB_HOST/DB_USER/DB_NAME/DB_PORT.
            secrets = {}
            if needs_db and database.db_secret:
                secrets["DB_PASSWORD"] = ecs.Secret.from_secrets_manager(
                    database.db_secret, field="password"
                )

            task.add_container(
                f"{name}Container",
                image=ecs.ContainerImage.from_asset(
                    os.path.join(ROOT, "services", image_subdir),
                    platform=ecr_assets.Platform.LINUX_AMD64,
                ),
                port_mappings=[ecs.PortMapping(container_port=port)],
                environment=env,
                secrets=secrets,
                logging=ecs.LogDrivers.aws_logs(
                    stream_prefix=name,
                    log_group=log_group,
                ),
            )

            # Cloud Map name: lowercase service name, e.g. "user-service"
            cloud_map_name = name.lower() + "-service"
            service = ecs.FargateService(
                self, f"{name}Service",
                cluster=cluster,
                task_definition=task,
                desired_count=1,
                security_groups=[ecs_sg],
                vpc_subnets=ec2.SubnetSelection(
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
                ),
                assign_public_ip=False,
                cloud_map_options=ecs.CloudMapOptions(
                    cloud_map_namespace=namespace,
                    name=cloud_map_name,
                    dns_ttl=Duration.seconds(10),
                ),
            )

            tg = elbv2.ApplicationTargetGroup(
                self, f"{name}Tg",
                vpc=network.vpc,
                port=port,
                protocol=elbv2.ApplicationProtocol.HTTP,
                targets=[service],
                health_check=elbv2.HealthCheck(
                    path="/health",
                    healthy_http_codes="200",
                ),
            )
            listener.add_action(
                f"{name}Rule",
                conditions=[elbv2.ListenerCondition.path_patterns(path_patterns)],
                priority=alb_priority,
                action=elbv2.ListenerAction.forward([tg]),
            )

        # ── Shared base env vars for every service ────────────────────────────
        db_host = database.database.db_instance_endpoint_address

        def base_env(port: int, extra: dict | None = None) -> dict:
            env = {
                "PORT":       str(port),
                "JWT_SECRET": jwt_secret,
                "REDIS_ADDR": database.redis_addr,
                # DB connection components (password injected via Secrets Manager)
                "DB_HOST": db_host,
                "DB_PORT": "5432",
                "DB_USER": "twitter",
                "DB_NAME": "twitter",
            }
            if extra:
                env.update(extra)
            return env

        # ── Register the 4 services ───────────────────────────────────────────
        _register_service(
            name="Gateway",
            port=8080,
            image_subdir="gateway",
            env=base_env(8080, {
                "USER_SERVICE_URL":     "http://user-service.mini-twitter.local:8081",
                "TWEET_SERVICE_URL":    "http://tweet-service.mini-twitter.local:8082",
                "TIMELINE_SERVICE_URL": "http://timeline-service.mini-twitter.local:8083",
                "RATE_LIMIT_RPM":       "5000",
            }),
            alb_priority=10,
            path_patterns=["/v1/*"],
            needs_db=False,   # gateway doesn't talk to DB directly
        )

        _register_service(
            name="User",
            port=8081,
            image_subdir="user",
            env=base_env(8081),
            alb_priority=20,
            path_patterns=["/v1/auth/*", "/v1/users/*"],
            needs_db=True,
        )

        _register_service(
            name="Tweet",
            port=8082,
            image_subdir="tweet",
            env=base_env(8082, {
                "USE_REDIS":        "true",
                "CONSISTENCY_MODE": "eventual",
            }),
            alb_priority=30,
            path_patterns=["/v1/tweets", "/v1/tweets/*"],
            needs_db=True,
        )

        _register_service(
            name="Timeline",
            port=8083,
            image_subdir="timeline",
            env=base_env(8083, {
                "USE_REDIS":         "true",
                "TWEET_SERVICE_URL": "http://tweet-service.mini-twitter.local:8082",
            }),
            alb_priority=40,
            path_patterns=["/v1/timeline/*"],
            needs_db=True,
        )

        # ── CloudFormation output ─────────────────────────────────────────────
        CfnOutput(
            self, "AlbDnsName",
            value=alb.load_balancer_dns_name,
            description="ALB DNS - set as VITE_API_BASE_URL for the frontend",
        )

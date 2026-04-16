import aws_cdk as cdk

from stacks.network_stack   import NetworkStack
from stacks.database_stack  import DatabaseStack
from stacks.container_stack import ContainerStack
from stacks.frontend_stack  import FrontendStack

app = cdk.App()

env = cdk.Environment(
    account=app.node.try_get_context("account"),
    region=app.node.try_get_context("region") or "us-east-1",
)

# ── Instantiate stacks in dependency order ────────────────────────────────────
network   = NetworkStack  (app, "NetworkStack",   env=env)
database  = DatabaseStack (app, "DatabaseStack",  network=network,             env=env)
container = ContainerStack(app, "ContainerStack", network=network, database=database, env=env)
frontend  = FrontendStack (app, "FrontendStack",  env=env)

# Tell CDK the explicit deployment order
database.add_dependency(network)
container.add_dependency(database)
# FrontendStack has no infra dependencies

app.synth()

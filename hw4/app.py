#!/usr/bin/env python3
import aws_cdk as cdk
from stack import Hw4Stack

app = cdk.App()
Hw4Stack(app, "HW4Stack")
app.synth()
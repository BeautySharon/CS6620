"""
CS6620 HW1 - AWS boto3 Assignment (in-class style)

This script performs:
1) Create IAM roles Dev and User
2) Attach policies (Dev: full S3, User: list/get only)
3) Create an IAM user
4) Use the created user to assume Dev role -> create bucket + upload objects
5) Assume User role -> list objects with prefix 'assignment' and compute total size
6) Assume Dev role again -> delete all objects and the bucket

Run:
    python3 assignment.py

Notes:
- Uses AWS CLI profile hardcoded as cs6620_admin
- Uses region hardcoded as us-west-2
- Leaves IAM resources (user/roles/policies) in place; use cleanup.py to remove them.
"""

import json
import time
import uuid

import boto3
import botocore
import os

# -----------------------------
# Settings
# -----------------------------
PROFILE = "cs6620_admin"
REGION = "us-west-2"


def assume_role_session(base_session: boto3.Session, role_arn: str, session_name: str) -> boto3.Session:
    """
    In-class style AssumeRole:
    - base_session.client('sts').assume_role(...)
    - create a new boto3.Session with temporary credentials
    """
    sts = base_session.client("sts")
    resp = sts.assume_role(RoleArn=role_arn, RoleSessionName=session_name)
    c = resp["Credentials"]
    return boto3.Session(
        aws_access_key_id=c["AccessKeyId"],
        aws_secret_access_key=c["SecretAccessKey"],
        aws_session_token=c["SessionToken"],
        region_name=REGION,
    )


def main():
    # Admin session (uses local AWS CLI profile)
    admin = boto3.Session(profile_name=PROFILE, region_name=REGION)
    iam = admin.client("iam")
    sts = admin.client("sts")

    acct_id = sts.get_caller_identity()["Account"]
    print(f"[INFO] Using account={acct_id}, region={REGION}")

    # ------------------------------------------------------------
    # 1) Create roles: Dev and User
    # ------------------------------------------------------------
    role_dev = "Dev"
    role_user = "User"

    # Trust policy: allow this AWS account (root principal) to assume role.
    # Then we grant the created IAM user permission to call sts:AssumeRole on these roles.
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"AWS": f"arn:aws:iam::{acct_id}:root"},
            "Action": "sts:AssumeRole",
        }]
    }

    def ensure_role(role_name: str) -> str:
        try:
            return iam.get_role(RoleName=role_name)["Role"]["Arn"]
        except iam.exceptions.NoSuchEntityException:
            resp = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description=f"{role_name} role for assignment",)
            print(f"[INFO] Created role {role_name}.")
            return resp["Role"]["Arn"]

    dev_role_arn = ensure_role(role_dev)
    user_role_arn = ensure_role(role_user)

    # ------------------------------------------------------------
    # 2) Attach policies:
    #    Dev -> AmazonS3FullAccess (managed)
    #    User -> inline list/get only (least privilege)
    # ------------------------------------------------------------

    # Dev: attach AWS managed policy
    iam.attach_role_policy(
        RoleName=role_dev,
        PolicyArn="arn:aws:iam::aws:policy/AmazonS3FullAccess"
    )
    print("[INFO] Attached AmazonS3FullAccess to Dev role.")

    # User: inline policy (list/get only)
    iam.put_role_policy(
        RoleName=role_user,
        PolicyName="UserS3ReadOnlyListGet",
        PolicyDocument=json.dumps({
            "Version": "2012-10-17",
            "Statement": [
                {"Effect": "Allow", "Action": "s3:ListAllMyBuckets", "Resource": "*"},
                {"Effect": "Allow", "Action": "s3:ListBucket", "Resource": "arn:aws:s3:::*"},
                {"Effect": "Allow", "Action": "s3:GetObject", "Resource": "arn:aws:s3:::*/*"},
            ],
     })
    )
    print("[INFO] Put inline policy on User role.")

    # ------------------------------------------------------------
    # 3) Create IAM user + allow it to assume Dev and User roles
    # ------------------------------------------------------------
    
    # Create IAM user
    iam_user_name = "assignment-user-1"
    try:
        iam.create_user(UserName=iam_user_name)
        print(f"[INFO] Created user: {iam_user_name}")
    except iam.exceptions.EntityAlreadyExistsException:
        print(f"[INFO] User already exists: {iam_user_name}")

    # Allow user to assume roles
    iam.put_user_policy(
        UserName=iam_user_name,
        PolicyName="AssumeRoles",
        PolicyDocument=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": "sts:AssumeRole",
                "Resource": [dev_role_arn, user_role_arn]
            }]
        })
    )

    # Create access key
    old_keys = iam.list_access_keys(UserName=iam_user_name)["AccessKeyMetadata"]
    for k in old_keys:
        iam.delete_access_key(UserName=iam_user_name, AccessKeyId=k["AccessKeyId"])

    key = iam.create_access_key(UserName=iam_user_name)["AccessKey"]

    created_user_session = boto3.Session(
        aws_access_key_id=key["AccessKeyId"],
        aws_secret_access_key=key["SecretAccessKey"],
        region_name=REGION,
    )

    time.sleep(10)


    # ------------------------------------------------------------
    # 4) Assume Dev role -> create bucket + upload objects
    # ------------------------------------------------------------

    # Assume Dev role -> S3 client
    dev_session = assume_role_session(created_user_session, dev_role_arn, "dev_role_assumed")
    s3 = dev_session.client("s3")

    # Unique bucket name
    bucket_name = f"assignment-{acct_id}-{uuid.uuid4().hex[:10]}"

    # Create bucket (us-east-1 不需要 LocationConstraint)
    kwargs = {"Bucket": bucket_name}
    if REGION != "us-east-1":
        kwargs["CreateBucketConfiguration"] = {"LocationConstraint": REGION}
    s3.create_bucket(**kwargs)

    # Create local txt files (in same folder as assignment.py)
    BASE_DIR = os.path.dirname(__file__)
    a1 = os.path.join(BASE_DIR, "assignment1.txt")
    a2 = os.path.join(BASE_DIR, "assignment2.txt")
    img = os.path.join(BASE_DIR, "recording1.jpg")

    # Upload local files
    s3.upload_file(a1, bucket_name, "assignment1.txt")
    s3.upload_file(a2, bucket_name, "assignment2.txt")
    s3.upload_file(img, bucket_name, "recording1.jpg")

    print("[STEP4] bucket:", bucket_name, "uploaded 3 objects")


    # ------------------------------------------------------------
    # 5) Assume User role -> list prefix 'assignment' and sum sizes
    # ------------------------------------------------------------
    user_session = assume_role_session(created_user_session, user_role_arn, "user_role_assumed")
    s3_user = user_session.client("s3")

    resp = s3_user.list_objects_v2(
        Bucket=bucket_name,
        Prefix="assignment"
    )

    total_size = sum(obj["Size"] for obj in resp.get("Contents", []))

    print(f"[RESULT] Total size for prefix 'assignment' = {total_size} bytes")

    # ------------------------------------------------------------
    # 6) Assume Dev role again -> delete all objects and bucket
    # ------------------------------------------------------------
    # Assume Dev role again -> cleanup
    dev_session2 = assume_role_session(created_user_session, dev_role_arn, "dev_role_cleanup")
    s3 = dev_session2.client("s3")

    print("[INFO] Cleaning up...")

    # list objects once (enough for this assignment)
    resp = s3.list_objects_v2(Bucket=bucket_name)
    objs = resp.get("Contents", [])

    if objs:
        s3.delete_objects(
            Bucket=bucket_name,
            Delete={"Objects": [{"Key": o["Key"]} for o in objs]}
        )

    s3.delete_bucket(Bucket=bucket_name)

    print("[INFO] Deleted bucket and objects successfully.")



if __name__ == "__main__":
    try:
        main()
    except botocore.exceptions.ClientError as e:
        print("[ERROR] AWS ClientError:", e)
        raise

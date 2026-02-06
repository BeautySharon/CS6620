"""
cleanup.py

Deletes:
- assignment-user-1
- Dev role
- User role
- any bucket starting with "assignment-"

Run:
    python3 cleanup.py
"""

import boto3
import botocore

PROFILE = "cs6620_admin"
REGION = "us-west-2"


def main():
    session = boto3.Session(profile_name=PROFILE, region_name=REGION)

    iam = session.client("iam")
    s3 = session.client("s3")

    print("Starting cleanup...\n")

    # -----------------------------
    # Delete Buckets
    # -----------------------------
    buckets = s3.list_buckets()["Buckets"]

    for b in buckets:
        name = b["Name"]

        if name.startswith("assignment-"):
            print("Deleting bucket:", name)

            # delete objects first
            resp = s3.list_objects_v2(Bucket=name)
            objs = resp.get("Contents", [])

            if objs:
                s3.delete_objects(
                    Bucket=name,
                    Delete={"Objects": [{"Key": o["Key"]} for o in objs]}
                )

            s3.delete_bucket(Bucket=name)

    # -----------------------------
    # Delete IAM user
    # -----------------------------
    user = "assignment-user-1"

    try:
        keys = iam.list_access_keys(UserName=user)["AccessKeyMetadata"]
        for k in keys:
            iam.delete_access_key(
                UserName=user,
                AccessKeyId=k["AccessKeyId"]
            )

        policies = iam.list_user_policies(UserName=user)["PolicyNames"]
        for p in policies:
            iam.delete_user_policy(
                UserName=user,
                PolicyName=p
            )

        iam.delete_user(UserName=user)

        print("Deleted IAM user:", user)

    except iam.exceptions.NoSuchEntityException:
        pass

    # -----------------------------
    # Delete roles
    # -----------------------------
    for role in ["Dev", "User"]:
        try:

            attached = iam.list_attached_role_policies(RoleName=role)["AttachedPolicies"]
            for pol in attached:
                iam.detach_role_policy(
                    RoleName=role,
                    PolicyArn=pol["PolicyArn"]
                )

            inline = iam.list_role_policies(RoleName=role)["PolicyNames"]
            for pol in inline:
                iam.delete_role_policy(
                    RoleName=role,
                    PolicyName=pol
                )

            iam.delete_role(RoleName=role)

            print("Deleted role:", role)

        except iam.exceptions.NoSuchEntityException:
            pass

    print("\n🔥 CLEANUP COMPLETE")
    

if __name__ == "__main__":
    main()
